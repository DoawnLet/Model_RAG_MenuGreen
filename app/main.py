"""
Menu Green - FastAPI Entry Point
Exposes the LangGraph orchestrator via REST API.
"""
from contextlib import asynccontextmanager
from typing import Optional, Literal, cast
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, BaseMessage
import json
import asyncio
import logging

from app.agents.orchestrator import orchestrator, AgentState
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient
from app.core.errors import (
    MenuGreenException,
    ErrorResponse,
    ErrorCode,
    GeminiAPIException,
    SupabaseException,
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
    print(f"📡 Supabase URL: {settings.supabase_url[:30]}..." if settings.supabase_url else "⚠️ Supabase not configured")
    yield
    # Shutdown
    print("🌿 Menu Green shutting down...")


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
# Exception Handlers
# ============================================================================

@app.exception_handler(MenuGreenException)
async def menu_green_exception_handler(request: Request, exc: MenuGreenException):
    """Handle custom Menu Green exceptions."""
    logger.error(f"MenuGreenException: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion
        ).model_dump()
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.error(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            code=ErrorCode.INVALID_INPUT,
            message=str(exc)
        ).model_dump()
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
            suggestion="Please try again later or contact support"
        ).model_dump()
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    user_id: Optional[str] = None
    conversation_history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""
    response: str
    intent: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


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
            user_profile = SupabaseClient.get_user_profile(request.user_id)
            tier = SupabaseClient.get_user_subscription(request.user_id)
            # Validate subscription tier
            if tier in ("free", "saving", "energy", "performance"):
                subscription_tier = tier
            inventory = SupabaseClient.get_user_inventory(request.user_id)
        
        # Prepare initial state
        initial_state = cast(AgentState, {
            "messages": messages,
            "user_id": request.user_id,
            "user_profile": user_profile,
            "intent": None,
            "subscription_tier": subscription_tier,
            "context": {"inventory": inventory},
        })
        
        # Invoke orchestrator
        result = orchestrator.invoke(initial_state)
        
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
            details={"error": str(e)}
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
            subscription_tier: Literal["free", "saving", "energy", "performance"] = "free"
            inventory = []
            
            if request.user_id:
                user_profile = SupabaseClient.get_user_profile(request.user_id)
                tier = SupabaseClient.get_user_subscription(request.user_id)
                if tier in ("free", "saving", "energy", "performance"):
                    subscription_tier = tier
                inventory = SupabaseClient.get_user_inventory(request.user_id)
            
            initial_state = cast(AgentState, {
                "messages": messages,
                "user_id": request.user_id,
                "user_profile": user_profile,
                "intent": None,
                "subscription_tier": subscription_tier,
                "context": {"inventory": inventory},
            })
            
            # True LangGraph streaming with astream()
            async for event in orchestrator.astream(initial_state):
                # Event structure: {node_name: output_dict}
                for node_name, node_output in event.items():
                    if "messages" in node_output:
                        # Extract the last message from this node
                        new_messages = node_output["messages"]
                        if new_messages and len(new_messages) > 0:
                            last_msg = new_messages[-1]
                            if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
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
# Run with: uvicorn app.main:app --reload
# ============================================================================
