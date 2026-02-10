import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.core.supabase_client import SupabaseClient, get_settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

async def verify_gemini():
    print("🧪 Verifying Google Gemini Integration...")
    
    settings = get_settings()
    print(f"🔑 API Key: {settings.google_api_key[:10]}...")
    print(f"🤖 LLM Model: {settings.llm_model}")
    print(f"🧠 Embedding Model: {settings.embedding_model}")
    
    # 1. Test Embeddings
    print("\n1. Testing Embeddings...")
    try:
        text = "Món ăn ngon Việt Nam"
        emb = await SupabaseClient.create_embedding(text)
        print(f"   ✅ Embedding generated. Dimension: {len(emb)}")
        if len(emb) != 768:
            print(f"   ⚠️ WARNING: Expected 768 dimensions for text-embedding-004, got {len(emb)}. Check model config.")
    except Exception as e:
        print(f"   ❌ Embedding failed: {e}")
        return

    # 2. Test Chat
    print("\n2. Testing Chat Generation...")
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key
        )
        response = await llm.ainvoke([HumanMessage(content="Chào bạn, bạn là ai?")])
        print(f"   ✅ Chat response: {response.content}")
    except Exception as e:
        print(f"   ❌ Chat failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_gemini())
