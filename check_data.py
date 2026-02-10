import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.core.supabase_client import SupabaseClient

async def check_recipes():
    print("Checking database content...")
    client = SupabaseClient.get_client()
    try:
        response = client.table("recipes").select("count", count="exact").execute()
        count = response.count
        print(f"Total recipes in DB: {count}")
    except Exception as e:
        print(f"Error checking recipes: {e}")

if __name__ == "__main__":
    asyncio.run(check_recipes())
