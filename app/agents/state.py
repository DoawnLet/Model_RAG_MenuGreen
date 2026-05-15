from typing import Annotated, Literal, Optional, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    State shared across all nodes in the graph.

    Attributes:
        messages: Conversation history (accumulates via add_messages)
        user_id: Current user's ID
        user_profile: User's nutrition profile (optional)
        intent: Detected user intent
        subscription_tier: User's subscription level
        context: Additional context data
        memory: Optional[str] # Retrieved memory context
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_id: Optional[str]
    user_profile: Optional[dict]
    intent: Optional[str]
    subscription_tier: Literal["free", "saving", "energy", "performance"]
    context: dict
    memory: Optional[str]
    intent_meta: Optional[dict]
