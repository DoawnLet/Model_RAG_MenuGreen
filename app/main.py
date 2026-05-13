"""
Menu Green - FastAPI Entry Point
Exposes the LangGraph orchestrator via REST API.
"""

from contextlib import asynccontextmanager
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, BaseMessage
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import logging
import time
import os
import sys
import logging
import time
import subprocess

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row, DictRow
from psycopg_pool import ConnectionPool

from app.agents.orchestrator import get_compiled_graph
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient
from app.core.errors import (
    MenuGreenException,
    ErrorResponse,
    ErrorCode,
)
from app.core.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    record_error,
    get_metrics,
    system_health,
)

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan & App Setup
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    settings = get_settings()
    print(f"🌿 {settings.app_name} starting...")
    print(
        f"📡 Supabase URL: {settings.supabase_url[:30]}..."
        if settings.supabase_url
        else "⚠️ Supabase not configured"
    )

    # Initialize Postgres Persistence
    if settings.postgres_url:
        print("💾 Initializing LangGraph Persistence...")
        # Use sync ConnectionPool with PostgresSaver (properly typed)
        pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
            conninfo=settings.postgres_url,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=False,
        )
        pool.open()
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()  # Create tables if not exist
        app.state.orchestrator = get_compiled_graph(checkpointer)
        app.state.db_pool = pool
    else:
        print("⚠️ No Postgres URL found. Persistence disabled.")
        app.state.orchestrator = get_compiled_graph(checkpointer=None)
        app.state.db_pool = None

    yield

    # Shutdown
    print("🌿 Menu Green shutting down...")
    if app.state.db_pool:
        app.state.db_pool.close()


app = FastAPI(
    title="Menu Green API",
    description="Hệ điều hành dinh dưỡng thông minh với Multi-Agent AI",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Monitoring Middleware (P2 Observability)
# ============================================================================


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track HTTP request metrics."""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    method = request.method
    endpoint = request.url.path
    status = response.status_code

    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
        duration
    )

    return response


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(MenuGreenException)
async def menu_green_exception_handler(request: Request, exc: MenuGreenException):
    """Handle custom Menu Green exceptions."""
    logger.error(f"MenuGreenException: {exc.code} - {exc.message}")

    # P2 Observability: Track error
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
    """Handle ValueError exceptions."""
    logger.error(f"ValueError: {str(exc)}")

    # P2 Observability: Track error
    record_error(error_type="ValueError", endpoint=request.url.path)

    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            code=ErrorCode.INVALID_INPUT, message=str(exc)
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            suggestion="Please try again later or contact support",
        ).model_dump(),
    )


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    conversation_history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str
    intent: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


# ─── Onboarding Models ───────────────────────────────────────────────────────


class OnboardingProfileRequest(BaseModel):
    """Form thu thập thông tin cá nhân người dùng."""

    user_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None  # "male" | "female" | "other"
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    activity_level: Optional[str] = None  # sedentary|light|moderate|active|very_active
    goal: Optional[str] = None  # lose_fat|maintain|gain_muscle
    dietary_preferences: Optional[list[str]] = None  # ["vegan", "gluten_free"]
    allergies: Optional[list[str]] = None  # ["seafood", "peanut"]


class InventoryItem(BaseModel):
    """Một nguyên liệu trong kho của user."""

    name: str
    quantity: float
    unit: str = "g"  # g, ml, pcs, ...
    expiry_date: Optional[str] = None  # "YYYY-MM-DD"
    category: Optional[str] = None  # "vegetable", "meat", "dairy", ...


class OnboardingInventoryRequest(BaseModel):
    """Danh sách nguyên liệu user nhập vào."""

    user_id: str
    items: list[InventoryItem]


# ============================================================================
# Endpoints
# ============================================================================


# ─── Onboarding Endpoints ────────────────────────────────────────────────────


@app.post("/onboarding/profile", status_code=201)
async def save_profile(request: OnboardingProfileRequest):
    """
    Lưu thông tin cá nhân người dùng (onboarding form).
    Dùng khi đăng nhập lần đầu hoặc cập nhật profile.
    """
    data = request.model_dump(exclude={"user_id"}, exclude_none=True)
    try:
        result = await SupabaseClient.upsert_user_profile_async(request.user_id, data)
        return {"success": True, "profile": result}
    except Exception as e:
        logger.error(f"Failed to save profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/onboarding/inventory", status_code=201)
async def save_inventory(request: OnboardingInventoryRequest):
    """
    Lưu danh sách nguyên liệu user đang có.
    """
    items = [item.model_dump() for item in request.items]
    try:
        await SupabaseClient.upsert_user_inventory_async(request.user_id, items)
        return {"success": True, "saved": len(items)}
    except Exception as e:
        logger.error(f"Failed to save inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/{user_id}/profile")
async def get_profile(user_id: str):
    """Lấy thông tin profile của user."""
    profile = await SupabaseClient.get_user_profile_async(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/user/{user_id}/inventory")
async def get_inventory(user_id: str):
    """Lấy danh sách nguyên liệu của user."""
    inventory = await SupabaseClient.get_user_inventory_async(user_id)
    return {"user_id": user_id, "items": inventory, "count": len(inventory)}


@app.post("/train/intent")
async def train_intent_model():
    """Trigger the local training script for the Intent Classifier."""
    try:
        def _run_training():
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "training", "train_intent_classifier.py"))
            return subprocess.run(
                [sys.executable, "-X", "utf8", script_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

        process = await run_in_threadpool(_run_training)
        
        if process.returncode == 0:
            return {"status": "success", "message": "Model trained successfully!", "details": process.stdout}
        else:
            raise HTTPException(status_code=500, detail=f"Training failed: {process.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/health/db")
async def health_check_db():
    """Database health check endpoint."""
    try:
        # Check Supabase connection (primary database)
        SupabaseClient.get_client().table("recipes").select("id").limit(1).execute()

        # Check optional PostgreSQL pool (for LangGraph persistence)
        postgres_status = "active" if app.state.db_pool else "disabled"

        system_health.set(1)  # P2 Observability
        return {
            "status": "healthy",
            "supabase": "connected",
            "postgres_pool": postgres_status,
            "note": "Postgres pool is optional for persistence only",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        system_health.set(0)  # P2 Observability
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
            },
        )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    P2 Observability: Expose all system metrics for scraping.
    """
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Sends user message to the orchestrator and returns AI response.
    """
    try:
        # Build conversation history
        messages: list[BaseMessage] = []
        if request.conversation_history:
            for msg in request.conversation_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg["content"]))

        # Add current message
        messages.append(HumanMessage(content=request.message))

        # Get user context if available
        user_profile = None
        subscription_tier: Literal["free", "saving", "energy", "performance"] = "free"
        inventory = []

        if request.user_id:
            # Parallelize Supabase calls for performance (P0 optimization)
            user_profile, tier, inventory = await asyncio.gather(
                SupabaseClient.get_user_profile_async(request.user_id),
                SupabaseClient.get_user_subscription_async(request.user_id),
                SupabaseClient.get_user_inventory_async(request.user_id),
            )
            # Validate subscription tier
            if tier in ("free", "saving", "energy", "performance"):
                subscription_tier = tier

        # Prepare initial state
        initial_state = {
            "messages": messages,
            "user_id": request.user_id,
            "user_profile": user_profile,
            "intent": None,
            "subscription_tier": subscription_tier,
            "context": {"inventory": inventory},
        }

        # Config for persistence
        thread_id = request.thread_id or request.user_id or "default_thread"
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke orchestrator with timeout (P0 reliability)
        try:
            result = await asyncio.wait_for(
                app.state.orchestrator.ainvoke(initial_state, config=config),
                timeout=120.0,  # 2 minutes timeout for complex meal planning
            )
        except asyncio.TimeoutError:
            logger.error(f"Orchestrator timeout after 120s for user {request.user_id}")
            raise MenuGreenException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Request timed out. Please try again or simplify your request.",
                details={"timeout": "120s"},
            )

        # Extract response
        ai_message = result["messages"][-1]

        return ChatResponse(
            response=ai_message.content,
            intent=result.get("intent"),
        )

    except MenuGreenException:
        # Re-raise custom exceptions to be handled by exception handler
        raise
    except Exception as e:
        logger.exception(f"Error in chat endpoint: {str(e)}")
        # Convert to generic MenuGreenException
        raise MenuGreenException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to process chat request",
            details={"error": str(e)},
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint.
    Returns response as Server-Sent Events for real-time display with true LangGraph streaming.
    """

    async def generate():
        try:
            # Build conversation history
            messages: list[BaseMessage] = []
            if request.conversation_history:
                for msg in request.conversation_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))

            # Add current message
            messages.append(HumanMessage(content=request.message))

            # Get user context if available
            user_profile = None
            subscription_tier: Literal["free", "saving", "energy", "performance"] = (
                "free"
            )
            inventory = []

            if request.user_id:
                # Parallelize Supabase calls for performance (P0 optimization)
                user_profile, tier, inventory = await asyncio.gather(
                    SupabaseClient.get_user_profile_async(request.user_id),
                    SupabaseClient.get_user_subscription_async(request.user_id),
                    SupabaseClient.get_user_inventory_async(request.user_id),
                )
                if tier in ("free", "saving", "energy", "performance"):
                    subscription_tier = tier

            initial_state = {
                "messages": messages,
                "user_id": request.user_id,
                "user_profile": user_profile,
                "intent": None,
                "subscription_tier": subscription_tier,
                "context": {"inventory": inventory},
            }

            # Config for persistence
            thread_id = request.thread_id or request.user_id or "default_thread"
            config = {"configurable": {"thread_id": thread_id}}

            # True LangGraph streaming with astream() and timeout tracking (P0 reliability)
            timeout_seconds = 120.0
            start_time = asyncio.get_event_loop().time()

            async for event in app.state.orchestrator.astream(
                initial_state, config=config
            ):
                # Check timeout during streaming
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    logger.error(
                        f"Orchestrator stream timeout after {timeout_seconds}s for user {request.user_id}"
                    )
                    yield f"data: {json.dumps({'error': f'Request timed out after {timeout_seconds}s', 'code': 'TIMEOUT'})}\n\n"
                    return

                # Event structure: {node_name: output_dict}
                for node_name, node_output in event.items():
                    if "messages" in node_output:
                        # Extract the last message from this node
                        new_messages = node_output["messages"]
                        if new_messages and len(new_messages) > 0:
                            last_msg = new_messages[-1]
                            if hasattr(last_msg, "content") and isinstance(
                                last_msg.content, str
                            ):
                                # Yield node progress
                                yield f"data: {json.dumps({'node': node_name, 'content': last_msg.content})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except MenuGreenException as e:
            logger.error(f"MenuGreenException in stream: {e.code} - {e.message}")
            yield f"data: {json.dumps({'error': e.message, 'code': e.code})}\n\n"
        except Exception as e:
            logger.exception(f"Unexpected error in stream: {str(e)}")
            yield f"data: {json.dumps({'error': 'An unexpected error occurred'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


# ============================================================================
# Static Files (Frontend UI)
# Mount this LAST so it doesn't override API routes!
# ============================================================================
os.makedirs("frontend", exist_ok=True)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# ============================================================================
# Run with: uvicorn app.main:app --reload
# ============================================================================
