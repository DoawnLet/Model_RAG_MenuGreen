"""
Shared API request/response models for the Menu Green worker API.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SubscriptionTier = Literal["free", "saving", "energy", "performance"]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    request_id: Optional[str] = None
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    request_id: Optional[str] = None
    thread_id: Optional[str] = None
    review_queued: bool = False
    intent_source: Optional[str] = None
    intent_confidence: Optional[float] = None


class WorkerChatResponse(BaseModel):
    request_id: str
    thread_id: str
    response: str
    intent: Optional[str] = None
    intent_source: Optional[str] = None
    intent_confidence: Optional[float] = None
    subscription_tier: SubscriptionTier = "free"
    duration_ms: float
    persistence_fallback_used: bool = False
    review_queued: bool = False
    source: str = "menu-green-ai-worker"


class HealthResponse(BaseModel):
    status: str
    version: str


class WorkerHealthResponse(HealthResponse):
    mode: str = "internal-ai-worker"


class OnboardingProfileRequest(BaseModel):
    user_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    dietary_preferences: Optional[list[str]] = None
    allergies: Optional[list[str]] = None


class InventoryItem(BaseModel):
    name: str
    quantity: float
    unit: str = "g"
    expiry_date: Optional[str] = None
    category: Optional[str] = None


class OnboardingInventoryRequest(BaseModel):
    user_id: str
    items: list[InventoryItem]
