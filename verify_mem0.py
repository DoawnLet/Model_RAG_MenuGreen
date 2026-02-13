import asyncio
import sys
import os

print("Importing config...")
try:
    from app.core.config import get_settings
    print("✅ Config imported")
except Exception as e:
    print(f"❌ Config import failed: {e}")

print("Importing get_memory_manager...")
try:
    from app.core.memory import get_memory_manager
    print("✅ Imported get_memory_manager")
except Exception as e:
    print(f"❌ Failed to import get_memory_manager: {e}")

print("Importing orchestrator...")
# Allow crash to see full traceback
from app.agents.orchestrator import orchestrator
print("✅ Imported orchestrator")

from langchain_core.messages import HumanMessage

async def test_direct_memory():
    print("\n🧠 Testing Direct Memory Access...")
    mm = get_memory_manager()
    user_id = "test_user_mem0"
    
    # 1. Add Memory
    # print("   Adding memory: 'Tôi bị dị ứng tôm và đậu phộng.'")
    # mm.add_memory(user_id, "User bị dị ứng tôm và đậu phộng.")
    
    # 2. Search Memory
    # print("   Searching memory for 'dị ứng'...")
    # memories = mm.search_memories(user_id, "dị ứng")
    # print(f"   Found {len(memories)} memories.")
    # for m in memories:
    #     print(f"   - {m}")
        
    # return len(memories) > 0

    # Adding memory
    try:
        print(f"   Adding memory for {user_id}...")
        mm.add_memory(user_id, "Tôi bị dị ứng tôm và đậu phộng.")
        print("✅ Memory added successfully")
    except Exception as e:
        print(f"⚠️ Memory add crash (expected on Windows shutdown?): {e}")

    print("\n🔍 Searching Memory...")
    # Search for allergies
    results = mm.search(query="Tôi bị dị ứng gì?", user_id=user_id)
    print(f"Results Type: {type(results)}")
    if hasattr(results, "keys"):
        print(f"Results Keys: {results.keys()}")
    
    # Handle list
    final_memories = []
    if isinstance(results, list):
        print(f"List length: {len(results)}")
        if len(results) > 0:
            print(f"First item: {results[0]} (Type: {type(results[0])})")
        final_memories = results
    elif isinstance(results, dict):
        # Maybe it's inside 'results' key?
        final_memories = results.get("results", []) or results.get("memories", [])
        if not final_memories and "memory" in results:
             final_memories = [results]

    if final_memories:
        found = False
        for r in final_memories:
            if isinstance(r, dict):
                mem_text = r.get("memory", "")
            elif isinstance(r, str):
                mem_text = r
            else:
                mem_text = str(r)
                
            if "tôm" in mem_text.lower():
                found = True
                break
        
        if found:
            print("✅ Correct memory retrieved!")
            return True
        else:
            print("❌ Memory not found in results.")
            return False
    else:
        print("❌ Results empty or not parsed.")
        return False   # Proceed to orchestrator test even if retrieval fails (for debug)
    return True

async def test_orchestrator_integration():
    print("\n🤖 Testing Orchestrator Integration...")
    user_id = "test_user_mem0"
    
    # query that should trigger memory retrieval
    message = "Gợi ý cho tôi một món ăn tối ngon."
    
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "subscription_tier": "free",
        "context": {}
    }
    
    print(f"   User: {message}")
    
    async for output in orchestrator.astream(initial_state):
        for key, value in output.items():
            print(f"   Node '{key}' executed.")
            if "messages" in value:
                print(f"   AI: {value['messages'][-1].content[:200]}...")
            if key == "__end__":
                print("   Flow ended.")

    # Check if the interaction was saved
    print("\n   Checking if conversation was saved to memory...")
    mm = get_memory_manager()
    # Search for the exact message to see if it was indexed
    recent = mm.search_memories(user_id, "món ăn tối")
    if recent:
        print("   ✅ Conversation context found in memory!")
    else:
        print("   ⚠️ Conversation context NOT found (async saving might be slow or failed).")

if __name__ == "__main__":
    # Clear old memory if possible (optional)
    # import shutil
    # if os.path.exists("./mem0_storage"):
    #     shutil.rmtree("./mem0_storage")
    
    success = asyncio.run(test_direct_memory())
    if success:
        asyncio.run(test_orchestrator_integration())
    else:
        print("❌ Direct specific memory test failed.")
