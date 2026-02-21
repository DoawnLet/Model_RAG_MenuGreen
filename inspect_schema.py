"""
Script to inspect actual Supabase database schema for recipes table.
"""
import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.core.config import get_settings
from supabase import create_client

async def inspect_schema():
    """Query Supabase to see actual schema."""
    print("🔍 Inspecting Supabase schema...")
    
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    try:
        from typing import cast, Any
        # Try to select all columns by selecting *
        result = supabase.table("recipes").select("*").limit(1).execute()
        
        if result.data:
            data = cast(list[dict[str, Any]], result.data)
            print("\n✅ Found recipes table. Sample record:")
            print(data[0])
            print("\n📋 Columns available:")
            for key in data[0].keys():
                print(f"  - {key}")
        else:
            print("\n⚠️ Table exists but is empty. Trying to get column info...")
            # Try inserting then deleting to see which columns are accepted
            test_recipe = {
                "name": "Test Recipe",
                "description": "Test"
            }
            result = supabase.table("recipes").insert(test_recipe).execute()
            if result.data:
                data = cast(list[dict[str, Any]], result.data)
                print("\n📋 Successfully inserted. Columns in response:")
                for key in data[0].keys():
                    print(f"  - {key}")
                # Delete the test recipe
                supabase.table("recipes").delete().eq("name", "Test Recipe").execute()
                print("\n🗑️ Test recipe deleted")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTrying alternative method...")
        
        # Try a minimal insert to see what's accepted
        minimal_recipe = {"name": "Minimal Test"}
        try:
            from typing import cast, Any
            result = supabase.table("recipes").insert(minimal_recipe).execute()
            print("✅ Minimal insert worked. Columns:")
            if result.data:
                data = cast(list[dict[str, Any]], result.data)
                for key in data[0].keys():
                    print(f"  - {key}")
            # Clean up
            supabase.table("recipes").delete().eq("name", "Minimal Test").execute()
        except Exception as e2:
            print(f"❌ Minimal insert also failed: {e2}")

if __name__ == "__main__":
    asyncio.run(inspect_schema())
