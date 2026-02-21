"""
Quick script to add a few test recipes to database.
"""
import asyncio
import sys
import os

sys.path.append(os.getcwd())

from app.core.config import get_settings
from supabase import create_client

async def quick_add_recipes():
    """Add a few hardcoded test recipes matching the actual database schema."""
    print("🚀 Quick ingestion starting...")
    
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    # Test recipes with only the fields that exist in schema
    recipes = [
        {
            "name": "Phở Bò",
            "description": "Món phở bò truyền thống Hà Nội với nước dùng ngọt thanh",
            "instructions": "1. Luộc xương để lấy nước dùng\n2. Nấu nước dùng với gia vị\n3. Trụng bánh phở\n4. Bày món với thịt bò, hành ngò",
            "prep_time_minutes": 30,
            "cook_time_minutes": 120,
            "servings": 4,
            "dietary_tags": ["high-protein", "warming", "vietnamese-classic"]
        },
        {
            "name": "Gỏi Cuốn Tôm Thịt",
            "description": "Gỏi cuốn tươi mát với tôm và thịt heo, ăn kèm nước mắm",
            "instructions": "1. Luộc tôm và thịt heo\n2. Chuẩn bị rau sống và bún\n3. Cuốn bánh tráng\n4. Ăn kèm với tương",
            "prep_time_minutes": 20,
            "cook_time_minutes": 15,
            "servings": 2,
            "dietary_tags": ["cooling", "fresh", "quick-lunch", "high-protein"]
        },
        {
            "name": "Cơm Tấm Sườn",
            "description": "Cơm tấm Sài Gòn với sườn nướng thơm lừng",
            "instructions": "1. Ướp sườn với gia vị\n2. Nướng sườn trên than hoa\n3. Chiên trứng ốp la\n4. Bày cơm với sườn, trứng và đồ chua",
            "prep_time_minutes": 15,
            "cook_time_minutes": 25,
            "servings": 1,
            "dietary_tags": ["high-protein", "office-friendly", "popular"]
        },
        {
            "name": "Canh Chua Cá Lóc",
            "description": "Canh chua cá lóc miền Nam với rau thơm và nước dùng chua ngọt",
            "instructions": "1. Làm sạch cá lóc\n2. Nấu nước dùng với me chua\n3. Cho cá và rau vào nấu\n4. Nêm nếm và thêm rau thơm",
            "prep_time_minutes": 15,
            "cook_time_minutes": 20,
            "servings": 4,
            "dietary_tags": ["warming", "high-protein", "vietnamese-classic", "no-sleepy"]
        },
        {
            "name": "Bún Chả Hà Nội",
            "description": "Bún chả đặc sản Hà Nội với chả nướng thơm phức",
            "instructions": "1. Ướp thịt với gia vị\n2. Nướng chả trên bếp than\n3. Pha nước mắm chua ngọt\n4. Bày bún với chả và rau sống",
            "prep_time_minutes": 25,
            "cook_time_minutes": 20,
            "servings": 2,
            "dietary_tags": ["high-protein", "office-friendly", "vietnamese-classic"]
        }
    ]
    
    print(f"📦 Inserting {len(recipes)} test recipes...")
    
    try:
        # Insert recipes without embeddings first (embeddings can be generated later)
        for recipe in recipes:
            result = supabase.table("recipes").insert(recipe).execute()
            print(f"✅ Added: {recipe['name']}")
        
        print(f"\n🎉 Successfully added {len(recipes)} recipes to database!")
        print("\n⚠️ Note: These recipes don't have embeddings yet.")
        print("Run the embedding generation script to enable vector search.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(quick_add_recipes())
