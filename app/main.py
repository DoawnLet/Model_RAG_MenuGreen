"""
Menu Green - FastAPI Entry Point
Exposes the LangGraph orchestrator via REST API.
"""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
import json
import asyncio

from app.agents.orchestrator import orchestrator, AgentState
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient


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
        messages = []
        if request.conversation_history:
            for msg in request.conversation_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=request.message))
        
        # Get user context if available
        user_profile = None
        subscription_tier = "free"
        inventory = []
        
        if request.user_id:
            user_profile = SupabaseClient.get_user_profile(request.user_id)
            subscription_tier = SupabaseClient.get_user_subscription(request.user_id)
            inventory = SupabaseClient.get_user_inventory(request.user_id)
        
        # Prepare initial state
        initial_state: AgentState = {
            "messages": messages,
            "user_id": request.user_id,
            "user_profile": user_profile,
            "intent": None,
            "subscription_tier": subscription_tier,
            "context": {"inventory": inventory},
        }
        
        # Invoke orchestrator
        result = orchestrator.invoke(initial_state)
        
        # Extract response
        ai_message = result["messages"][-1]
        
        return ChatResponse(
            response=ai_message.content,
            intent=result.get("intent"),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint.
    Returns response as Server-Sent Events for real-time display.
    """
    async def generate():
        try:
            # Build initial state (same as /chat)
            messages = [HumanMessage(content=request.message)]
            
            initial_state: AgentState = {
                "messages": messages,
                "user_id": request.user_id,
                "user_profile": None,
                "intent": None,
                "subscription_tier": "free",
                "context": {},
            }
            
            # Stream the response
            # Note: Full streaming requires async graph execution
            result = orchestrator.invoke(initial_state)
            response_text = result["messages"][-1].content
            
            # Simulate streaming by yielding chunks
            words = response_text.split()
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i:i+3])
                yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.05)
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


# ============================================================================
# Run with: uvicorn app.main:app --reload
# ============================================================================
