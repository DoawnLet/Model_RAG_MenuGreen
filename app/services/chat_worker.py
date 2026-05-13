"""
Internal chat worker service used by both legacy local endpoints and the
new C#-facing worker API.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.api_models import ChatRequest, SubscriptionTier
from app.core.config import get_settings
from app.core.errors import ErrorCode, MenuGreenException
from app.core.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


@dataclass
class ChatExecutionResult:
    request_id: str
    thread_id: str
    response: str
    intent: str | None
    subscription_tier: SubscriptionTier
    duration_ms: float
    persistence_fallback_used: bool


def _is_valid_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def build_messages(request: ChatRequest) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for message in request.conversation_history:
        if message.role == "user":
            messages.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            messages.append(AIMessage(content=message.content))
        else:
            messages.append(SystemMessage(content=message.content))

    messages.append(HumanMessage(content=request.message))
    return messages


async def load_user_context(
    user_id: str | None,
) -> tuple[dict | None, SubscriptionTier, list[dict]]:
    if not _is_valid_uuid(user_id):
        return None, "free", []

    user_profile, tier, inventory = await asyncio.gather(
        SupabaseClient.get_user_profile_async(user_id),
        SupabaseClient.get_user_subscription_async(user_id),
        SupabaseClient.get_user_inventory_async(user_id),
    )

    subscription_tier: SubscriptionTier = "free"
    if tier in ("free", "saving", "energy", "performance"):
        subscription_tier = tier

    return user_profile, subscription_tier, inventory


def build_initial_state(
    request: ChatRequest,
    messages: list[BaseMessage],
    user_profile: dict | None,
    subscription_tier: SubscriptionTier,
    inventory: list[dict],
) -> dict:
    return {
        "messages": messages,
        "user_id": request.user_id,
        "user_profile": user_profile,
        "intent": None,
        "subscription_tier": subscription_tier,
        "context": {"inventory": inventory},
    }


async def invoke_orchestrator(app, initial_state: dict, config: dict) -> tuple[dict, bool]:
    settings = get_settings()
    timeout_seconds = settings.worker_timeout_seconds
    fallback_used = False

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(app.state.orchestrator.invoke, initial_state, config),
            timeout=timeout_seconds,
        )
        return result, fallback_used
    except Exception as invoke_error:
        fallback_graph = getattr(app.state, "orchestrator_fallback", None)
        persistence_error = str(invoke_error)
        if fallback_graph is not None and (
            "checkpoint" in persistence_error.lower()
            or "jsonb_each_text" in persistence_error
            or "operator does not exist: bytea -> unknown" in persistence_error
            or type(invoke_error).__name__ == "NotImplementedError"
        ):
            logger.warning(
                "Persistence-backed invoke failed, retrying without persistence: %s",
                persistence_error,
            )
            fallback_used = True
            result = await asyncio.wait_for(
                fallback_graph.ainvoke(initial_state, config=config),
                timeout=timeout_seconds,
            )
            return result, fallback_used
        if isinstance(invoke_error, asyncio.TimeoutError):
            raise
        raise
    except asyncio.TimeoutError as exc:
        raise MenuGreenException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Request timed out. Please try again or simplify your request.",
            details={"timeout_seconds": timeout_seconds},
        ) from exc


async def execute_chat(app, request: ChatRequest) -> ChatExecutionResult:
    request_id = request.request_id or str(uuid.uuid4())
    thread_id = request.thread_id or request.user_id or request_id

    messages = build_messages(request)
    user_profile, subscription_tier, inventory = await load_user_context(request.user_id)
    initial_state = build_initial_state(
        request=request,
        messages=messages,
        user_profile=user_profile,
        subscription_tier=subscription_tier,
        inventory=inventory,
    )
    config = {"configurable": {"thread_id": thread_id}}

    loop = asyncio.get_running_loop()
    start = loop.time()
    result, fallback_used = await invoke_orchestrator(app, initial_state, config)
    duration_ms = (loop.time() - start) * 1000

    ai_message = result["messages"][-1]
    response_text = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)

    return ChatExecutionResult(
        request_id=request_id,
        thread_id=thread_id,
        response=response_text,
        intent=result.get("intent"),
        subscription_tier=subscription_tier,
        duration_ms=round(duration_ms, 2),
        persistence_fallback_used=fallback_used,
    )
