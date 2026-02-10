"""
LangGraph Orchestrator - The central brain of Menu Green.
Implements a Hub-and-Spoke model for routing user requests to specialized agents.
"""
from typing import Annotated, Literal, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
import re

from app.agents.nutrition import (
    UserProfile, 
    calculate_macros, 
    get_nutrition_summary,
)
from app.agents.inventory import (
    InventoryItem,
    check_expiry_status,
    format_inventory_alert,
)
from app.agents.rag_tool import format_recipe_results, RAGTool
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient
from app.agents.web_browser import browse_url


# ============================================================================
# State Definition
# ============================================================================

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
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: Optional[str]
    user_profile: Optional[dict]
    intent: Optional[str]
    subscription_tier: Literal["free", "saving", "energy", "performance"]
    context: dict


# ============================================================================
# Intent Classification
# ============================================================================

INTENT_PROMPT = """
Bạn là một hệ thống phân loại ý định người dùng cho ứng dụng dinh dưỡng Menu Green.

Phân loại tin nhắn của người dùng vào MỘT trong các danh mục sau:
- "recipe_search": Người dùng muốn tìm công thức nấu ăn hoặc đề xuất món ăn
- "web_browsing": Người dùng cung cấp URL hoặc yêu cầu đọc/tóm tắt từ link
- "nutrition_calc": Người dùng muốn tính toán dinh dưỡng (BMR, TDEE, macro)
- "inventory_check": Người dùng muốn kiểm tra nguyên liệu hoặc hạn sử dụng
- "meal_plan": Người dùng muốn lập kế hoạch bữa ăn
- "general": Câu hỏi chung về sức khỏe, dinh dưỡng
- "unknown": Không liên quan đến app

Chỉ trả lời bằng MỘT từ duy nhất là tên danh mục.
"""


def classify_intent(state: AgentState) -> AgentState:
    """
    Classify user intent from the latest message.
    
    This node analyzes the user's message and determines which 
    specialized agent should handle it.
    """
    settings = get_settings()
    
    # Heuristic: If message contains http/https, likely web browsing
    last_message = state["messages"][-1].content
    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
    if re.search(url_pattern, last_message):
        return {"intent": "web_browsing"}

    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",  # Use fast model for classification
        google_api_key=settings.google_api_key,
        temperature=0,
    )
    
    response = llm.invoke([
        {"role": "system", "content": INTENT_PROMPT},
        {"role": "user", "content": last_message},
    ])
    
    intent = response.content.strip().lower()
    
    # Validate intent
    valid_intents = ["recipe_search", "nutrition_calc", "inventory_check", 
                     "meal_plan", "general", "web_browsing", "unknown"]
    if intent not in valid_intents:
        valid_found = False
        for valid in valid_intents:
            if valid in intent:
                intent = valid
                valid_found = True
                break
        if not valid_found:
            intent = "general"
    
    return {"intent": intent}


# ============================================================================
# Permission Check
# ============================================================================

TIER_PERMISSIONS = {
    "free": ["recipe_search", "general", "unknown", "web_browsing"],
    "saving": ["recipe_search", "general", "unknown", "inventory_check", "web_browsing"],
    "energy": ["recipe_search", "general", "unknown", "inventory_check", "meal_plan", "web_browsing"],
    "performance": ["recipe_search", "general", "unknown", "inventory_check", 
                    "meal_plan", "nutrition_calc", "web_browsing"],
}


def check_permissions(state: AgentState) -> bool:
    """Check if user's subscription tier allows the detected intent."""
    tier = state.get("subscription_tier", "free")
    intent = state.get("intent", "general")
    
    allowed = TIER_PERMISSIONS.get(tier, TIER_PERMISSIONS["free"])
    return intent in allowed


# ============================================================================
# Agent Nodes
# ============================================================================

def nutrition_agent(state: AgentState) -> AgentState:
    """
    Handle nutrition calculation requests.
    Requires user profile data.
    """
    profile_data = state.get("user_profile")
    
    if not profile_data:
        response = "❌ Chưa có thông tin hồ sơ sức khỏe. Vui lòng cập nhật hồ sơ trước."
    else:
        try:
            profile = UserProfile(**profile_data)
            response = get_nutrition_summary(profile)
        except Exception as e:
            response = f"❌ Lỗi khi tính toán: {str(e)}"
    
    return {"messages": [AIMessage(content=response)]}


def inventory_agent(state: AgentState) -> AgentState:
    """
    Handle inventory-related queries.
    Checks expiration dates and alerts user.
    """
    # In production, fetch from Supabase
    # For now, return placeholder
    inventory_items = state.get("context", {}).get("inventory", [])
    
    if not inventory_items:
        response = "📦 Kho nguyên liệu của bạn đang trống. Hãy thêm nguyên liệu!"
    else:
        items = [InventoryItem(**item) for item in inventory_items]
        status = check_expiry_status(items)
        response = format_inventory_alert(status)
    
    return {"messages": [AIMessage(content=response)]}


async def recipe_agent(state: AgentState) -> AgentState:
    """
    Handle recipe search requests using RAG.
    Available to all tiers.
    """
    try:
        # Initialize RAG Tool
        # In a real app, inject this or use a singleton to avoid re-init
        client = SupabaseClient.get_client()
        rag = RAGTool(client, SupabaseClient.create_embedding)
        
        last_message = state["messages"][-1].content
        
        # Search for recipes (using 5 results by default)
        # We search by raw text since we don't have an entity extractor yet
        recipes = await rag.search_by_text(last_message, limit=3)
        
        response = format_recipe_results(recipes)
        
        # Add context-aware suggestion if user has inventory
        inventory = state.get("context", {}).get("inventory", [])
        if inventory and not recipes:
            response += "\n\n💡 Gợi ý: Hãy thử tìm món ăn với nguyên liệu bạn đang có!"
            
    except Exception as e:
        response = f"❌ Lỗi khi tìm kiếm công thức: {str(e)}"
        
    return {"messages": [AIMessage(content=response)]}


async def web_browsing_agent(state: AgentState) -> AgentState:
    """
    Handle web browsing requests.
    Extracts URL, crawls content, and summarizes/answers using LLM.
    """
    last_message = state["messages"][-1].content
    
    # 1. Extract URL
    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*"
    urls = re.findall(url_pattern, last_message)
    
    if not urls:
        return {"messages": [AIMessage(content="❌ Không tìm thấy đường dẫn (URL) hợp lệ trong tin nhắn.")]}
    
    url = urls[0] # Process the first URL found
    
    # 2. Browse Content
    raw_content = await browse_url(url)
    
    # 3. Process with LLM
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
    )
    
    # Limit content length to avoid context overflow (approx 10k chars)
    truncated_content = raw_content[:20000] 
    
    system_prompt = """
    Bạn là trợ lý nghiên cứu web. Nhiệm vụ của bạn là đọc nội dung Markdown từ trang web 
    và trả lời yêu cầu của người dùng dựa trên nội dung đó.
    
    Nếu là công thức nấu ăn, hãy tóm tắt theo format: Tên, Nguyên liệu, Cách làm.
    Nếu nội dung quá dài, hãy tóm tắt các ý chính.
    """
    
    response = await llm.ainvoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Yêu cầu của người dùng: {last_message}\n\nNội dung trang web:\n{truncated_content}"}
    ])
    
    return {"messages": [AIMessage(content=response.content)]}


def general_agent(state: AgentState) -> AgentState:
    """
    Handle general questions with a conversational LLM.
    """
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
    )
    
    system_message = """
    Bạn là trợ lý dinh dưỡng Menu Green. Trả lời ngắn gọn, thân thiện về 
    các câu hỏi liên quan đến sức khỏe và dinh dưỡng.
    """
    
    response = llm.invoke([
        {"role": "system", "content": system_message},
        *[{"role": "user" if isinstance(m, HumanMessage) else "assistant", 
           "content": m.content} for m in state["messages"][-5:]]  # Last 5 messages
    ])
    
    return {"messages": [AIMessage(content=response.content)]}


def permission_denied_agent(state: AgentState) -> AgentState:
    """
    Handle requests that require higher subscription tier.
    """
    intent = state.get("intent", "unknown")
    tier = state.get("subscription_tier", "free")
    
    upgrade_messages = {
        "nutrition_calc": "🔒 Tính năng tính toán dinh dưỡng chính xác cần gói **Hiệu suất**.",
        "inventory_check": "🔒 Tính năng quản lý kho cần gói **Tiết kiệm** trở lên.",
        "meal_plan": "🔒 Tính năng lập kế hoạch bữa ăn cần gói **Năng lượng** trở lên.",
    }
    
    response = upgrade_messages.get(
        intent, 
        "🔒 Tính năng này cần nâng cấp gói dịch vụ."
    )
    response += "\n\n💡 Nâng cấp ngay để trải nghiệm đầy đủ sức mạnh của Menu Green!"
    
    return {"messages": [AIMessage(content=response)]}


# ============================================================================
# Router Logic
# ============================================================================

def route_by_intent(state: AgentState) -> str:
    """
    Conditional edge: Route to appropriate agent based on intent and permissions.
    """
    if not check_permissions(state):
        return "permission_denied"
    
    intent = state.get("intent", "general")
    
    routes = {
        "recipe_search": "recipe",
        "web_browsing": "web_browsing",
        "nutrition_calc": "nutrition",
        "inventory_check": "inventory",
        "meal_plan": "general",  # TODO: Implement meal planner
        "general": "general",
        "unknown": "general",
    }
    
    return routes.get(intent, "general")


# ============================================================================
# Graph Construction
# ============================================================================

def create_orchestrator() -> StateGraph:
    """
    Build the LangGraph orchestrator.
    
    Graph Structure:
    
    [START] -> [classify_intent] -> [route_by_intent] -> [agent_node] -> [END]
                                         |
                                         v
                              [permission_denied] -> [END]
    """
    # Initialize graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("nutrition", nutrition_agent)
    workflow.add_node("inventory", inventory_agent)
    workflow.add_node("recipe", recipe_agent)
    workflow.add_node("web_browsing", web_browsing_agent)
    workflow.add_node("general", general_agent)
    workflow.add_node("permission_denied", permission_denied_agent)
    
    # Set entry point
    workflow.set_entry_point("classify_intent")
    
    # Add conditional edges from classifier
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "nutrition": "nutrition",
            "inventory": "inventory",
            "recipe": "recipe",
            "web_browsing": "web_browsing",
            "general": "general",
            "permission_denied": "permission_denied",
        }
    )
    
    # All agents end the conversation turn
    workflow.add_edge("nutrition", END)
    workflow.add_edge("inventory", END)
    workflow.add_edge("recipe", END)
    workflow.add_edge("web_browsing", END)
    workflow.add_edge("general", END)
    workflow.add_edge("permission_denied", END)
    
    return workflow.compile()


# Singleton instance
orchestrator = create_orchestrator()
