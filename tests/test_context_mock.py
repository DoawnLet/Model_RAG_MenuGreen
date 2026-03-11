import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Import dependencies we need to patch or use
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.rag_tool import RecipeMatch

# Import the orchestrator (it will have the real imports)
from app.agents.orchestrator import orchestrator

async def test_context_logic_mocks():
    print("🚀 Starting Logic Verification (with Explicit Mocks)...\n")
    
    # --- SCENE 1: Recipe Search with Context ---
    print("--- SCENE 1: Recipe Search with Context ---")
    
    # Create explicit mocks
    mock_rag_instance = MagicMock()
    # Explicitly set search_by_text to return a coroutine
    mock_rag_instance.search_by_text = AsyncMock(return_value=[
        RecipeMatch(id="1", name="Gà Kho Gừng", description="Món gà kho ấm bụng", similarity_score=0.9)
    ])
    
    # Mock LLM response
    mock_llm_instance = MagicMock()
    # invoke is sync in ChatOpenAI
    mock_llm_instance.invoke.return_value = AIMessage(content="recipe_search")
    
    # Apply patches to the NAMES in orchestrator module
    with patch("app.agents.orchestrator.SupabaseClient") as MockSupabase, \
         patch("app.agents.orchestrator.RAGTool", return_value=mock_rag_instance) as MockRAG, \
         patch("app.agents.orchestrator.ChatOpenAI", return_value=mock_llm_instance) as MockLLM:
            
        state_1 = {
            "messages": [HumanMessage(content="Gợi ý món gà")],
            "user_id": "test_user",
            "subscription_tier": "free",
            "intent": "recipe_search", 
            "context": {
                "inventory": [{"name": "chicken"}]
            }
        }
        
        # Run Scene 1
        result = await orchestrator.ainvoke(state_1)
        response = result["messages"][-1].content
        
        # Write response to file to avoid truncation issues
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(response)

        print(f"Agent Response:\n{response[:100]}...\n") # Print start to terminal
        
        if "Gà Kho Gừng" in response:
            print("✅ Context Logic Verified: Agent suggested recipe from RAG tool.")
        else:
            print("❌ Verification Failed: Response didn't contain expected recipe.")
            # Print failure reason if any
            if "❌ Lỗi" in response:
                print(f"   Error in response: {response}")

if __name__ == "__main__":
    asyncio.run(test_context_logic_mocks())
