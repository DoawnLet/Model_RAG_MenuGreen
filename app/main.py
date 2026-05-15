"""
Menu Green FastAPI entry point.

This app now favors an internal AI worker mode so a C# gateway can call it
through a stable JSON contract. The lightweight local frontend remains
optional for development only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.agents.orchestrator import get_compiled_graph
from app.api_models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    OnboardingInventoryRequest,
    OnboardingProfileRequest,
    WorkerChatResponse,
    WorkerHealthResponse,
)
from app.core.config import get_settings
from app.core.errors import ErrorCode, ErrorResponse, MenuGreenException
from app.core.metrics import (
    get_metrics,
    http_request_duration_seconds,
    http_requests_total,
    record_error,
    system_health,
)
from app.core.supabase_client import SupabaseClient
from app.services.chat_worker import build_initial_state, build_messages, execute_chat, load_user_context

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("%s starting in internal AI worker mode", settings.app_name)
    if settings.supabase_url:
        logger.info("Supabase configured")
    else:
        logger.warning("Supabase not configured")

    if settings.postgres_url:
        logger.info("Initializing LangGraph persistence")
        pool: ConnectionPool[Connection[DictRow]] | None = None
        try:
            pool = ConnectionPool(
                conninfo=settings.postgres_url,
                kwargs={"row_factory": dict_row, "autocommit": True},
                open=False,
            )
            pool.open()
            checkpointer = PostgresSaver(pool)
            checkpointer.setup()
            app.state.orchestrator = get_compiled_graph(checkpointer)
            app.state.orchestrator_fallback = get_compiled_graph(checkpointer=None)
            app.state.db_pool = pool
        except Exception as exc:
            logger.warning("Postgres persistence disabled due to setup error: %s", exc)
            if pool is not None:
                try:
                    pool.close()
                except Exception:
                    pass
            app.state.orchestrator = get_compiled_graph(checkpointer=None)
            app.state.orchestrator_fallback = app.state.orchestrator
            app.state.db_pool = None
    else:
        logger.info("No Postgres URL found. Persistence disabled.")
        app.state.orchestrator = get_compiled_graph(checkpointer=None)
        app.state.orchestrator_fallback = app.state.orchestrator
        app.state.db_pool = None

    yield

    logger.info("%s shutting down", settings.app_name)
    if getattr(app.state, "db_pool", None):
        app.state.db_pool.close()


settings = get_settings()
app = FastAPI(
    title="Menu Green AI Worker API",
    description="Internal AI worker for chat, recipes, nutrition, and planning",
    version=APP_VERSION,
    lifespan=lifespan,
)

allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = asyncio.get_running_loop().time()
    response = await call_next(request)
    duration = asyncio.get_running_loop().time() - start_time

    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    return response


@app.exception_handler(MenuGreenException)
async def menu_green_exception_handler(request: Request, exc: MenuGreenException):
    logger.error("MenuGreenException: %s - %s", exc.code, exc.message)
    record_error(error_type="MenuGreenException", endpoint=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion,
        ).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.error("ValueError: %s", exc)
    record_error(error_type="ValueError", endpoint=request.url.path)
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(code=ErrorCode.INVALID_INPUT, message=str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error: %s", exc)
    record_error(error_type=type(exc).__name__, endpoint=request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            suggestion="Please try again later or contact support",
        ).model_dump(),
    )


@app.post("/onboarding/profile", status_code=201)
async def save_profile(request: OnboardingProfileRequest):
    data = request.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        result = await SupabaseClient.upsert_user_profile_async(request.user_id, data)
        return {"success": True, "profile": result}
    except Exception as exc:
        logger.error("Failed to save profile: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/onboarding/inventory", status_code=201)
async def save_inventory(request: OnboardingInventoryRequest):
    items = [item.model_dump() for item in request.items]
    try:
        await SupabaseClient.upsert_user_inventory_async(request.user_id, items)
        return {"success": True, "saved": len(items)}
    except Exception as exc:
        logger.error("Failed to save inventory: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/user/{user_id}/profile")
async def get_profile(user_id: str):
    profile = await SupabaseClient.get_user_profile_async(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/user/{user_id}/inventory")
async def get_inventory(user_id: str):
    inventory = await SupabaseClient.get_user_inventory_async(user_id)
    return {"user_id": user_id, "items": inventory, "count": len(inventory)}


@app.post("/train/intent")
async def train_intent_model():
    if not settings.enable_training_endpoint:
        raise HTTPException(status_code=404, detail="Training endpoint is disabled")

    try:
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "training", "train_intent_classifier.py")
        )
        process = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-X", "utf8", script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode == 0:
            return {"status": "success", "message": "Model trained successfully", "details": process.stdout}
        raise HTTPException(status_code=500, detail=f"Training failed: {process.stderr}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version=APP_VERSION)


@app.get("/worker/health", response_model=WorkerHealthResponse)
async def worker_health_check():
    return WorkerHealthResponse(status="healthy", version=APP_VERSION)


@app.get("/health/db")
async def health_check_db():
    try:
        SupabaseClient.get_client().table("recipes").select("id").limit(1).execute()
        postgres_status = "active" if getattr(app.state, "db_pool", None) else "disabled"
        system_health.set(1)
        return {
            "status": "healthy",
            "supabase": "connected",
            "postgres_pool": postgres_status,
            "mode": "internal-ai-worker",
        }
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        system_health.set(0)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "error": str(exc)},
        )


@app.get("/metrics")
async def metrics():
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


@app.post("/worker/chat", response_model=WorkerChatResponse)
async def worker_chat(request: ChatRequest, http_request: Request):
    try:
        result = await execute_chat(app, request)
        response = WorkerChatResponse(
            request_id=result.request_id,
            thread_id=result.thread_id,
            response=result.response,
            intent=result.intent,
            intent_source=result.intent_source,
            intent_confidence=result.intent_confidence,
            subscription_tier=result.subscription_tier,
            duration_ms=result.duration_ms,
            persistence_fallback_used=result.persistence_fallback_used,
            review_queued=result.review_queued,
        )
        json_response = JSONResponse(content=response.model_dump())
        json_response.headers["X-Request-Id"] = result.request_id
        return json_response
    except MenuGreenException:
        raise
    except Exception as exc:
        logger.exception("Error in worker chat endpoint: %s", exc)
        raise MenuGreenException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to process worker chat request",
            details={"path": str(http_request.url.path), "error": str(exc)},
        ) from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await execute_chat(app, request)
        return ChatResponse(
            response=result.response,
            intent=result.intent,
            request_id=result.request_id,
            thread_id=result.thread_id,
            review_queued=result.review_queued,
            intent_source=result.intent_source,
            intent_confidence=result.intent_confidence,
        )
    except MenuGreenException:
        raise
    except Exception as exc:
        logger.exception("Error in chat endpoint: %s", exc)
        raise MenuGreenException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to process chat request",
            details={"error": str(exc)},
        ) from exc


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        try:
            messages = build_messages(request)
            user_profile, subscription_tier, inventory = await load_user_context(request.user_id)
            initial_state = build_initial_state(
                request=request,
                messages=messages,
                user_profile=user_profile,
                subscription_tier=subscription_tier,
                inventory=inventory,
            )
            thread_id = request.thread_id or request.user_id or "default_thread"
            config = {"configurable": {"thread_id": thread_id}}

            timeout_seconds = settings.worker_timeout_seconds
            start_time = asyncio.get_running_loop().time()

            async for event in app.state.orchestrator.astream(initial_state, config=config):
                if asyncio.get_running_loop().time() - start_time > timeout_seconds:
                    yield f"data: {json.dumps({'error': f'Request timed out after {timeout_seconds}s', 'code': 'TIMEOUT'})}\n\n"
                    return

                for node_name, node_output in event.items():
                    if "messages" not in node_output:
                        continue
                    new_messages = node_output["messages"]
                    if not new_messages:
                        continue
                    last_msg = new_messages[-1]
                    if hasattr(last_msg, "content") and isinstance(last_msg.content, str):
                        yield f"data: {json.dumps({'node': node_name, 'content': last_msg.content})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"
        except MenuGreenException as exc:
            yield f"data: {json.dumps({'error': exc.message, 'code': exc.code})}\n\n"
        except Exception as exc:
            logger.exception("Unexpected error in stream: %s", exc)
            yield f"data: {json.dumps({'error': 'An unexpected error occurred'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if settings.serve_frontend and os.path.isdir("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
