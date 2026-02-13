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
import logging

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
from app.agents.meal_planner import (
    nutrition_analyzer_agent,
    recipe_retriever_agent,
    meal_planner_agent,
    recipe_adapter_agent,
    validation_shopping_agent,
)
from app.core.retry_utils import with_retry, safe_llm_call


logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================

from app.agents.state import AgentState



# ============================================================================
# Intent Classification
# ============================================================================

INTENT_PROMPT = """
Bạn là hệ thống phân loại ý định người dùng cho ứng dụng dinh dưỡng Menu Green.

NHIỆM VỤ: Phân loại tin nhắn vào MỘT trong các intent sau:

1. **recipe_search**: Tìm công thức, đề xuất món ăn, hỏi cách nấu
   Ví dụ: "Món gì ngon cho bữa trưa?", "Cách làm phở bò", "Món ăn với gà"

2. **web_browsing**: Cung cấp URL hoặc yêu cầu đọc/tóm tắt link
   Ví dụ: "Đọc bài này giúp tôi: https://...", "Tóm tắt link này"

3. **nutrition_calc**: Tính toán BMR/TDEE/macros, phân tích dinh dưỡng cá nhân
   Ví dụ: "Tính BMR cho tôi", "Tôi cần bao nhiêu protein?", "TDEE của tôi là gì?"

4. **inventory_check**: Kiểm tra kho nguyên liệu, hạn sử dụng
   Ví dụ: "Nguyên liệu nào sắp hết hạn?", "Kiểm tra tủ lạnh", "Còn gì trong kho?"

5. **meal_plan**: Lập kế hoạch bữa ăn 7 ngày
   Ví dụ: "Lên thực đơn tuần", "Kế hoạch ăn giảm cân", "Meal prep cho 1 tuần"

6. **general**: Câu hỏi chung về sức khỏe, dinh dưỡng, lời khuyên
   Ví dụ: "Ăn gì để tăng cơ?", "Chế độ ăn cho người tiểu đường", "Lợi ích của rau xanh"

7. **unknown**: Không liên quan đến ứng dụng
   Ví dụ: "Thời tiết hôm nay", "Ai thắng World Cup?"

OUTPUT FORMAT: Chỉ trả về TÊN INTENT (1 từ) - không giải thích.

VÍ DỤ:
User: "Món gì ngon cho bữa tối?"
Assistant: recipe_search

User: "Lên thực đơn giảm cân cho tôi"
Assistant: meal_plan

User: "Tính BMR của tôi"
Assistant: nutrition_calc
"""


def classify_intent(state: AgentState) -> dict:
    """
    Classify user intent from the latest message.
    
    This node analyzes the user's message and determines which 
    specialized agent should handle it.
    """
    from app.core.memory import get_memory_manager
    settings = get_settings()
    
    # --- MEMORY INJECTION ---
    user_id = state.get("user_id") or "default_user"
    memory_manager = get_memory_manager()
    # Fetch relevant memories (e.g. top 5) based on the last message
    last_msg_content = state["messages"][-1].content
    if isinstance(last_msg_content, str):
        memories = memory_manager.get_formatted_context(user_id, last_msg_content)
    else:
        memories = ""
    
    # Update state with memory
    # Note: In a real LangGraph, we might want to do this in a separate node, 
    # but doing it here saves a step.
    state["memory"] = memories
    # ------------------------

    # Heuristic: If message contains http/https, likely web browsing
    last_message = state["messages"][-1]
    # Type guard: ensure content is string
    if not isinstance(last_message.content, str):
        return {"intent": "general"}
    
    message_content: str = last_message.content
    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
    if re.search(url_pattern, message_content):
        return {"intent": "web_browsing"}

    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=0,
    )
    
    response = llm.invoke([
        {"role": "system", "content": INTENT_PROMPT},
        {"role": "user", "content": message_content},
    ])
    
    # Type guard: ensure response content is string
    if not isinstance(response.content, str):
        return {"intent": "general"}
    
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

def nutrition_agent(state: AgentState) -> dict:
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


def inventory_agent(state: AgentState) -> dict:
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


async def recipe_agent(state: AgentState) -> dict:
    """
    Handle recipe search requests using RAG with retry logic.
    Available to all tiers.
    """
    try:
        # Inject Memory
        user_memory = state.get("memory", "")
        
        # Initialize RAG Tool
        client = SupabaseClient.get_client()
        rag = RAGTool(client, SupabaseClient.create_embedding)
        
        last_message = state["messages"][-1]
        # Type guard: ensure content is string
        if not isinstance(last_message.content, str):
            return {"messages": [AIMessage(content="❌ Không thể xử lý tin nhắn này.")]}
        
        message_content: str = last_message.content
        
        # Wrap RAG search with retry decorator
        @with_retry(max_attempts=3, base_delay=1.0)
        async def search_with_retry():
            return await rag.search_by_text(message_content, limit=3)
        
        recipes = await search_with_retry()
        response = format_recipe_results(recipes)
        
        # Add context-aware suggestion if user has inventory
        inventory = state.get("context", {}).get("inventory", [])
        if inventory and not recipes:
            response += "\n\n💡 Gợi ý: Hãy thử tìm món ăn với nguyên liệu bạn đang có!"
            
        if user_memory:
             response += f"\n\n(Lưu ý từ ký ức: {user_memory})"

    except Exception as e:
        logger.error(f"Recipe agent failed: {e}")
        response = f"❌ Lỗi khi tìm kiếm công thức. Vui lòng thử lại sau."
        
    return {"messages": [AIMessage(content=response)]}


async def web_browsing_agent(state: AgentState) -> dict:
    """
    Handle web browsing requests.
    Extracts URL, crawls content, and summarizes/answers using LLM.
    """
    last_message = state["messages"][-1]
    # Type guard: ensure content is string
    if not isinstance(last_message.content, str):
        return {"messages": [AIMessage(content="❌ Không thể xử lý tin nhắn này.")]}
    
    message_content: str = last_message.content
    
    # 1. Extract URL
    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*"
    urls = re.findall(url_pattern, message_content)
    
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
        {"role": "user", "content": f"Yêu cầu của người dùng: {message_content}\n\nNội dung trang web:\n{truncated_content}"}
    ])
    
    return {"messages": [AIMessage(content=response.content)]}


def general_agent(state: AgentState) -> dict:
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
    
    THÔNG TIN CÁ NHÂN (Ký ức):
    {state.get("memory", "")}
    """
    
    response = llm.invoke([
        {"role": "system", "content": system_message},
        *[{"role": "user" if isinstance(m, HumanMessage) else "assistant", 
           "content": m.content} for m in state["messages"][-5:]]  # Last 5 messages
    ])
    
    return {"messages": [AIMessage(content=response.content)]}


def permission_denied_agent(state: AgentState) -> dict:
    """
    Handle requests that require higher subscription tier.
    """
    intent = state.get("intent") or "unknown"
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
# Memory Node
# ============================================================================



def save_memory_node(state: AgentState) -> dict:
    """
    Node to save the interaction to memory.
    """
    from app.core.memory import get_memory_manager
    
    user_id = state.get("user_id") or "default_user"
    last_user_msg = None
    last_ai_msg = None
    
    # Find last user and AI message
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage) and not last_user_msg:
            last_user_msg = m.content
        if isinstance(m, AIMessage) and not last_ai_msg:
            last_ai_msg = m.content
        if last_user_msg and last_ai_msg:
            break
            
    if last_user_msg and last_ai_msg:
        try:
            memory_manager = get_memory_manager()
            # Combine Q&A for better context
            interaction = f"User: {last_user_msg}\nAI: {last_ai_msg}"
            memory_manager.add_memory(user_id, interaction)
            logger.info(f"💾 Memory saved for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save memory: {e}")
            
    return {} # Does not modify state keys

# ============================================================================
# Router Logic
# ============================================================================

def route_by_intent(state: AgentState) -> str:
    """
    Conditional edge: Route to appropriate agent based on intent and permissions.
    """
    if not check_permissions(state):
        return "permission_denied"
    
    intent = state.get("intent") or "general"
    
    routes = {
        "recipe_search": "recipe",
        "web_browsing": "web_browsing",
        "nutrition_calc": "nutrition",
        "inventory_check": "inventory",
        "meal_plan": "meal_plan_workflow",  # 5-step meal planning pipeline
        "general": "general",
        "unknown": "general",
    }
    
    return routes.get(intent, "general")


# ============================================================================
# Meal Planning Subgraph
# ============================================================================

def create_meal_plan_subgraph():
    """
    Create 5-step meal planning subgraph.
    
    Pipeline:
    nutrition_analyzer → recipe_retriever → meal_planner 
    → recipe_adapter → validation_shopping → END
    """
    subgraph = StateGraph(AgentState)
    
    # Add 5 agent nodes
    subgraph.add_node("nutrition_analyzer", nutrition_analyzer_agent)
    subgraph.add_node("recipe_retriever", recipe_retriever_agent)
    subgraph.add_node("meal_planner", meal_planner_agent)
    subgraph.add_node("recipe_adapter", recipe_adapter_agent)
    subgraph.add_node("validation_shopping", validation_shopping_agent)
    
    # Set entry point
    subgraph.set_entry_point("nutrition_analyzer")
    
    # Sequential pipeline edges
    subgraph.add_edge("nutrition_analyzer", "recipe_retriever")
    subgraph.add_edge("recipe_retriever", "meal_planner")
    subgraph.add_edge("meal_planner", "recipe_adapter")
    subgraph.add_edge("recipe_adapter", "validation_shopping")
    subgraph.add_edge("validation_shopping", END)
    
    return subgraph.compile()


# ============================================================================
# Graph Construction
# ============================================================================

def create_orchestrator(checkpointer=None):
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
    workflow.add_node("meal_plan_workflow", create_meal_plan_subgraph())
    workflow.add_node("save_memory", save_memory_node)
    
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
            "meal_plan_workflow": "meal_plan_workflow",
            "general": "general",
            "permission_denied": "permission_denied",
        }
    )
    
    # All agents end the conversation turn
    # All agents go to save_memory instead of END
    workflow.add_edge("nutrition", "save_memory")
    workflow.add_edge("inventory", "save_memory")
    workflow.add_edge("recipe", "save_memory")
    workflow.add_edge("web_browsing", "save_memory")
    workflow.add_edge("general", "save_memory")
    workflow.add_edge("meal_plan_workflow", "save_memory")
    
    # Permission denied usually doesn't need memory saving, but can link if needed
    workflow.add_edge("permission_denied", END)
    
    # Save memory ends the flow
    workflow.add_edge("save_memory", END)
    
    return workflow.compile(checkpointer=checkpointer)


# Export the graph builder for external compilation if needed,
# or use a factory function in main.py
def get_compiled_graph(checkpointer=None):
    """Factory to get the compiled graph, optionally with persistence."""
    workflow = create_orchestrator(checkpointer)
    return workflow

# Create default instance
orchestrator = create_orchestrator()
