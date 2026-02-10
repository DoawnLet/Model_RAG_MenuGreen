import asyncio
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.core.config import get_settings

settings = get_settings()
API_KEY = settings.google_api_key

async def test_generation():
    print("\n--- Testing Generation (gemini-1.5-flash) ---")
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=API_KEY)
        resp = await llm.ainvoke([HumanMessage(content="Hello")])
        print(f"✅ Success: {resp.content}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

async def test_embedding(model_name):
    print(f"\n--- Testing Embedding ({model_name}) ---")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=API_KEY)
        vec = await embeddings.aembed_query("Hello world")
        print(f"✅ Success! Dimension: {len(vec)}")
    except Exception as e:
        print(f"❌ Failed: {e}")

async def main():
    if await test_generation():
        models = [
            "models/embedding-001",
            "embedding-001",
            "models/text-embedding-004",
            "text-embedding-004"
        ]
        for m in models:
            await test_embedding(m)
    else:
        print("Skipping embedding tests due to generation failure.")

if __name__ == "__main__":
    asyncio.run(main())
