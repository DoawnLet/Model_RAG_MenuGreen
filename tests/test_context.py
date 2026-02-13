import asyncio
import os
from dotenv import load_dotenv

# Load env before imports
load_dotenv()

from langchain_core.messages import HumanMessage
from app.agents.orchestrator import orchestrator

async def test_context_awareness():
    print("🚀 Starting Context Awareness Test...\n")
    
    # Scene 1: Recipe Search with Context
    print("--- SCENE 1: Recipe Search with Context ---")
    state_1 = {
        "messages": [HumanMessage(content="Gợi ý món ăn từ gà")],
        "user_id": "test_user",
        "user_profile": None,
        "subscription_tier": "free",
        "intent": "recipe_search", # Pre-set to skip classifier/router for unit test focus, or let it route
        "context": {
            "inventory": [
                {"name": "chicken", "quantity": 1.0, "unit": "kg", "expiry_date": "2025-12-31"}
            ]
        }
    }
    
    # We can invoke the whole graph, or just the node. 
    # Let's invoke the whole graph to test routing too.
    # Note: classify_intent might overwrite our manual intent, which is fine.
    
    # For robust testing, let's run the graph.
    print(f"User Input: {state_1['messages'][-1].content}")
    print(f"Context: {state_1['context']}")
    
    result_1 = await orchestrator.ainvoke(state_1)
    response_1 = result_1["messages"][-1].content
    print(f"\nAgent Response:\n{response_1}\n")
    
    
    # Scene 2: Inventory Check (Permission Denied for Free Tier)
    print("--- SCENE 2: Inventory Check (Free Tier) ---")
    state_2 = {
        "messages": [HumanMessage(content="Kiểm tra tủ lạnh của tôi")],
        "user_id": "test_user",
        "subscription_tier": "free", # Free tier matches 'inventory_check' -> permission_denied?
        # TIER_PERMISSIONS: free -> [recipe_search, general, unknown]
        # inventory_check is NOT in free.
        "context": {}
    }
    
    print(f"User Input: {state_2['messages'][-1].content}")
    print(f"Subscription: {state_2['subscription_tier']}")
    
    result_2 = await orchestrator.ainvoke(state_2)
    response_2 = result_2["messages"][-1].content
    print(f"\nAgent Response:\n{response_2}\n")


if __name__ == "__main__":
    asyncio.run(test_context_awareness())
