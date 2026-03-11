"""
Metrics and Observability Module for Menu Green.
Provides Prometheus metrics, OpenTelemetry tracing, and cost tracking.

P2 Feature: Comprehensive monitoring for production deployment.
"""

import time
import logging
from functools import wraps
from typing import Callable
from contextlib import contextmanager

# Prometheus metrics
from prometheus_client import (  # type: ignore
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Request metrics
http_requests_total = Counter(
    "menu_green_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "menu_green_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

# LLM metrics
llm_calls_total = Counter(
    "menu_green_llm_calls_total", "Total LLM API calls", ["model", "agent", "status"]
)

llm_call_duration_seconds = Histogram(
    "menu_green_llm_call_duration_seconds", "LLM API call latency", ["model", "agent"]
)

llm_tokens_used_total = Counter(
    "menu_green_llm_tokens_used_total",
    "Total tokens consumed",
    ["model", "type"],  # metric type: input/output
)

llm_cost_usd_total = Counter(
    "menu_green_llm_cost_usd_total", "Total LLM cost in USD", ["model"]
)

# Agent execution metrics
agent_execution_duration_seconds = Histogram(
    "menu_green_agent_execution_seconds",
    "Agent execution time",
    ["agent_name", "intent"],
)

agent_executions_total = Counter(
    "menu_green_agent_executions_total",
    "Total agent executions",
    ["agent_name", "status"],
)

# RAG metrics
rag_searches_total = Counter(
    "menu_green_rag_searches_total",
    "Total RAG searches",
    ["search_type"],  # by_text, by_ingredients
)

rag_search_duration_seconds = Histogram(
    "menu_green_rag_search_duration_seconds", "RAG search latency", ["search_type"]
)

# Database metrics
db_queries_total = Counter(
    "menu_green_db_queries_total", "Total database queries", ["operation", "table"]
)

db_query_duration_seconds = Histogram(
    "menu_green_db_query_duration_seconds",
    "Database query latency",
    ["operation", "table"],
)

# Memory/Cache metrics
memory_cache_hits_total = Counter(
    "menu_green_memory_cache_hits_total", "Memory cache hits"
)

memory_cache_misses_total = Counter(
    "menu_green_memory_cache_misses_total", "Memory cache misses"
)

memory_cache_size = Gauge("menu_green_memory_cache_size", "Current memory cache size")

# Error metrics
errors_total = Counter(
    "menu_green_errors_total", "Total errors", ["error_type", "endpoint"]
)

# System info
system_info = Info("menu_green_system", "System information")

# Set system info
system_info.info(
    {
        "version": "0.1.0",
        "framework": "LangGraph 1.0.8",
        "llm": "Gemini 2.5 Flash",
        "embeddings": "Gemini Embedding-001",
    }
)


# ============================================================================
# Cost Tracking
# ============================================================================

# Gemini API pricing (as of Feb 2026)
GEMINI_PRICING = {
    "gemini-2.0-flash-exp": {
        "input": 0.075 / 1_000_000,  # $0.075 per 1M input tokens
        "output": 0.30 / 1_000_000,  # $0.30 per 1M output tokens
    },
    "text-embedding-004": {
        "input": 0.00002 / 1_000,  # $0.00002 per 1K tokens
        "output": 0.0,
    },
    "embedding-001": {
        "input": 0.00002 / 1_000,  # $0.00002 per 1K tokens
        "output": 0.0,
    },
}


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for LLM API call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    if model not in GEMINI_PRICING:
        logger.warning(f"Unknown model for cost calculation: {model}")
        return 0.0

    pricing = GEMINI_PRICING[model]
    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]

    return input_cost + output_cost


def track_llm_cost(model: str, input_tokens: int, output_tokens: int):
    """Track LLM cost in metrics.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    """
    cost = calculate_llm_cost(model, input_tokens, output_tokens)

    llm_cost_usd_total.labels(model=model).inc(cost)
    llm_tokens_used_total.labels(model=model, type="input").inc(input_tokens)
    llm_tokens_used_total.labels(model=model, type="output").inc(output_tokens)


# ============================================================================
# Decorators for Tracking
# ============================================================================


def track_llm_call(model: str, agent: str):
    """Decorator to track LLM API calls.

    Usage:
        @track_llm_call(model="gemini-2.0-flash-exp", agent="classify_intent")
        async def call_llm():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)

                # Try to extract token usage if available
                if hasattr(result, "usage_metadata"):
                    usage = result.usage_metadata
                    input_tokens = getattr(usage, "prompt_token_count", 0)
                    output_tokens = getattr(usage, "candidates_token_count", 0)

                    track_llm_cost(model, input_tokens, output_tokens)

                return result

            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                llm_calls_total.labels(model=model, agent=agent, status=status).inc()
                llm_call_duration_seconds.labels(model=model, agent=agent).observe(
                    duration
                )

        return wrapper

    return decorator


def track_agent_execution(agent_name: str):
    """Decorator to track agent execution time.

    Usage:
        @track_agent_execution("recipe_agent")
        async def recipe_agent(state):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            intent = "unknown"

            # Try to extract intent from state
            if args and len(args) > 0:
                state = args[0]
                if isinstance(state, dict):
                    intent = state.get("intent", "unknown")

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                agent_executions_total.labels(
                    agent_name=agent_name, status=status
                ).inc()
                agent_execution_duration_seconds.labels(
                    agent_name=agent_name, intent=intent
                ).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            intent = "unknown"

            if args and len(args) > 0:
                state = args[0]
                if isinstance(state, dict):
                    intent = state.get("intent", "unknown")

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                agent_executions_total.labels(
                    agent_name=agent_name, status=status
                ).inc()
                agent_execution_duration_seconds.labels(
                    agent_name=agent_name, intent=intent
                ).observe(duration)

        # Check if function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextmanager
def track_db_query(operation: str, table: str):
    """Context manager to track database queries.

    Usage:
        with track_db_query('select', 'recipes'):
            results = supabase.table('recipes').select('*').execute()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        db_queries_total.labels(operation=operation, table=table).inc()
        db_query_duration_seconds.labels(operation=operation, table=table).observe(
            duration
        )


@contextmanager
def track_rag_search(search_type: str):
    """Context manager to track RAG searches.

    Usage:
        with track_rag_search('by_text'):
            results = await rag.search_by_text(query)
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        rag_searches_total.labels(search_type=search_type).inc()
        rag_search_duration_seconds.labels(search_type=search_type).observe(duration)


# ============================================================================
# Cache Metrics Helpers
# ============================================================================


def record_cache_hit():
    """Record a cache hit."""
    memory_cache_hits_total.inc()


def record_cache_miss():
    """Record a cache miss."""
    memory_cache_misses_total.inc()


def update_cache_size(size: int):
    """Update current cache size.

    Args:
        size: Number of items in cache
    """
    memory_cache_size.set(size)


# ============================================================================
# Error Tracking
# ============================================================================


def record_error(error_type: str, endpoint: str):
    """Record an error occurrence.

    Args:
        error_type: Type of error (e.g., 'MenuGreenException', 'ValueError')
        endpoint: Endpoint where error occurred
    """
    errors_total.labels(error_type=error_type, endpoint=endpoint).inc()


# ============================================================================
# Metrics Export
# ============================================================================


def get_metrics() -> tuple[bytes, str]:
    """Get Prometheus metrics in text format.

    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST


# ============================================================================
# Cost Summary
# ============================================================================


def get_cost_summary() -> dict[str, float | dict[str, float]]:
    """Get summary of LLM costs.

    Returns:
        Dictionary with cost breakdown by model
    """
    # Note: In production, you'd query the actual metric values
    # For now, return structure
    return {
        "total_usd": 0.0,
        "by_model": {
            "gemini-2.0-flash-exp": 0.0,
            "text-embedding-004": 0.0,
        },
    }


# ============================================================================
# Health Check Metrics
# ============================================================================

system_health = Gauge(
    "menu_green_system_health", "System health status (1=healthy, 0=unhealthy)"
)

# Set initial health to healthy
system_health.set(1)


def set_system_health(healthy: bool):
    """Update system health status.

    Args:
        healthy: Whether system is healthy
    """
    system_health.set(1 if healthy else 0)
