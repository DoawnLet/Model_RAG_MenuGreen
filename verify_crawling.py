import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.agents.orchestrator import orchestrator
from langchain_core.messages import HumanMessage

async def test_crawling():
    print("🕸️ Testing Web Browsing Agent with Jina Reader...")
    
    # Test URL: A real recipe link (or any link)
    url = "https://www.cooky.vn/cong-thuc/ba-chi-heo-khia-nuoc-dua-22442" # Example URL
    # If this specific URL is dead, any article URL works
    
    message = f"Hãy đọc công thức từ link này và tóm tắt các bước chính: {url}"
    
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "user_id": "test_user",
        "user_profile": None,
        "subscription_tier": "free",
        "context": {}
    }
    
    print(f"User > {message}\n")
    
    try:
        # Run the graph
        async for output in orchestrator.astream(initial_state):
            for key, value in output.items():
                print(f"🤖 Node '{key}' executed.")
                if "messages" in value:
                    last_msg = value["messages"][-1]
                    print(f"\nAnswer:\n{last_msg.content[:500]}...\n(truncated)")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_crawling())
