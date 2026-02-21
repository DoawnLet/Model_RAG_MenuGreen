"""
Hướng dẫn Insert Data vào Database Menu Green
==============================================

Thứ tự insert phải tuân theo foreign key dependencies:

1. user_profiles       (Không phụ thuộc)
2. ingredients         (Không phụ thuộc)
3. recipes             (Không phụ thuộc)
4. user_subscriptions  (→ user_profiles)
5. recipe_ingredients  (→ recipes, ingredients)
6. user_inventory      (→ user_profiles, ingredients)
7. meal_plans          (→ user_profiles)
8. meal_plan_meals     (→ meal_plans, recipes)
9. shopping_lists      (→ meal_plans, user_profiles)
10. daily_logs         (→ user_profiles)

QUAN TRỌNG: Chạy schema_fixes.sql TRƯỚC để fix RLS và embedding dimension!
"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta
from uuid import UUID
from typing import cast, Any

sys.path.append(os.getcwd())

from app.core.config import get_settings
from supabase import create_client


class DataInserter:
    """Helper class để insert data theo đúng thứ tự."""
    
    def __init__(self):
        settings = get_settings()
        self.supabase = create_client(settings.supabase_url, settings.supabase_key)
        self.user_ids = []
        self.recipe_ids = []
        self.ingredient_ids = []
        self.meal_plan_ids = []
    
    # =========================================================================
    # BƯỚC 1: User Profiles (Base table - no dependencies)
    # =========================================================================
    
    def insert_user_profiles(self):
        """Insert user profiles - Bước đầu tiên."""
        print("\n📋 BƯỚC 1: Inserting User Profiles...")
        
        users = [
            {
                "name": "Nguyễn Văn An",
                "age": 28,
                "gender": "male",
                "height_cm": 175,
                "weight_kg": 70,
                "activity_level": "moderate",
                "goal": "maintain",
                "dietary_preferences": ["vietnamese"],
                "allergies": []
            },
            {
                "name": "Trần Thị Bình",
                "age": 32,
                "gender": "female",
                "height_cm": 160,
                "weight_kg": 55,
                "activity_level": "active",
                "goal": "lose_fat",
                "dietary_preferences": ["low_carb"],
                "allergies": ["peanuts"]
            }
        ]
        
        try:
            result = self.supabase.table("user_profiles").insert(users).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            self.user_ids = [user["id"] for user in data]
            print(f"   ✅ Inserted {len(data)} users")
            for user in data:
                print(f"      → {user['name']} (ID: {user['id'][:8]}...)")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 2: Ingredients (Base table - no dependencies)
    # =========================================================================
    
    def insert_ingredients(self):
        """Insert ingredients - Bước thứ hai."""
        print("\n🥒 BƯỚC 2: Inserting Ingredients...")
        
        ingredients = [
            {
                "name": "Thịt bò",
                "calories_per_100g": 250,
                "protein_per_100g": 26,
                "carbs_per_100g": 0,
                "fat_per_100g": 15,
                "fiber_per_100g": 0,
                "category": "Thịt"
            },
            {
                "name": "Cà chua",
                "calories_per_100g": 18,
                "protein_per_100g": 0.9,
                "carbs_per_100g": 3.9,
                "fat_per_100g": 0.2,
                "fiber_per_100g": 1.2,
                "category": "Rau củ"
            },
            {
                "name": "Gạo",
                "calories_per_100g": 130,
                "protein_per_100g": 2.7,
                "carbs_per_100g": 28,
                "fat_per_100g": 0.3,
                "fiber_per_100g": 0.4,
                "category": "Tinh bột"
            },
            {
                "name": "Trứng gà",
                "calories_per_100g": 155,
                "protein_per_100g": 13,
                "carbs_per_100g": 1.1,
                "fat_per_100g": 11,
                "fiber_per_100g": 0,
                "category": "Đạm"
            }
        ]
        
        try:
            result = self.supabase.table("ingredients").insert(ingredients).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            self.ingredient_ids = [ing["id"] for ing in data]
            print(f"   ✅ Inserted {len(data)} ingredients")
            for ing in data:
                print(f"      → {ing['name']} ({ing['calories_per_100g']} cal/100g)")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 3: Recipes (Base table - no dependencies)
    # =========================================================================
    
    def insert_recipes(self):
        """Insert recipes - Bước thứ ba."""
        print("\n🍲 BƯỚC 3: Inserting Recipes...")
        
        recipes = [
            {
                "name": "Phở Bò",
                "description": "Món phở bò truyền thống Hà Nội",
                "instructions": "1. Luộc xương\n2. Nấu nước dùng\n3. Trụng bánh phở\n4. Bày món",
                "prep_time_minutes": 30,
                "cook_time_minutes": 120,
                "servings": 4,
                "dietary_tags": ["high-protein", "warming"]
            },
            {
                "name": "Cơm Tấm Sườn",
                "description": "Cơm tấm Sài Gòn với sườn nướng",
                "instructions": "1. Ướp sườn\n2. Nướng sườn\n3. Chiên trứng\n4. Bày cơm",
                "prep_time_minutes": 15,
                "cook_time_minutes": 25,
                "servings": 1,
                "dietary_tags": ["high-protein", "office-friendly"]
            }
        ]
        
        try:
            result = self.supabase.table("recipes").insert(recipes).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            self.recipe_ids = [recipe["id"] for recipe in data]
            print(f"   ✅ Inserted {len(data)} recipes")
            for recipe in data:
                print(f"      → {recipe['name']} ({recipe['servings']} servings)")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 4: User Subscriptions (→ user_profiles)
    # =========================================================================
    
    def insert_user_subscriptions(self):
        """Insert user subscriptions - Phụ thuộc user_profiles."""
        print("\n💳 BƯỚC 4: Inserting User Subscriptions...")
        
        if not self.user_ids:
            print("   ⚠️ Skipped: No users found")
            return []
        
        subscriptions = [
            {
                "user_id": self.user_ids[0],
                "tier": "energy",
                "is_active": True
            },
            {
                "user_id": self.user_ids[1],
                "tier": "free",
                "is_active": True
            }
        ]
        
        try:
            result = self.supabase.table("user_subscriptions").insert(subscriptions).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} subscriptions")
            for sub in data:
                print(f"      → Tier: {sub['tier']} (User: {sub['user_id'][:8]}...)")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 5: Recipe Ingredients (→ recipes, ingredients)
    # =========================================================================
    
    def insert_recipe_ingredients(self):
        """Insert recipe ingredients - Phụ thuộc recipes và ingredients."""
        print("\n🥗 BƯỚC 5: Inserting Recipe Ingredients...")
        
        if not self.recipe_ids or not self.ingredient_ids:
            print("   ⚠️ Skipped: No recipes or ingredients found")
            return []
        
        # Phở Bò = Thịt bò + Gạo (bánh phở)
        # Cơm Tấm = Gạo + Trứng
        recipe_ingredients = [
            {
                "recipe_id": self.recipe_ids[0],  # Phở Bò
                "ingredient_id": self.ingredient_ids[0],  # Thịt bò
                "amount": 300,
                "unit": "g"
            },
            {
                "recipe_id": self.recipe_ids[0],  # Phở Bò
                "ingredient_id": self.ingredient_ids[2],  # Gạo (bánh phở)
                "amount": 200,
                "unit": "g"
            },
            {
                "recipe_id": self.recipe_ids[1],  # Cơm Tấm
                "ingredient_id": self.ingredient_ids[2],  # Gạo
                "amount": 150,
                "unit": "g"
            },
            {
                "recipe_id": self.recipe_ids[1],  # Cơm Tấm
                "ingredient_id": self.ingredient_ids[3],  # Trứng
                "amount": 2,
                "unit": "quả"
            }
        ]
        
        try:
            result = self.supabase.table("recipe_ingredients").insert(recipe_ingredients).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} recipe-ingredient links")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 6: User Inventory (→ user_profiles, ingredients)
    # =========================================================================
    
    def insert_user_inventory(self):
        """Insert user inventory - Phụ thuộc user_profiles và ingredients."""
        print("\n🏪 BƯỚC 6: Inserting User Inventory...")
        
        if not self.user_ids or not self.ingredient_ids:
            print("   ⚠️ Skipped: No users or ingredients found")
            return []
        
        # User 1 có thịt bò và cà chua
        inventory = [
            {
                "user_id": self.user_ids[0],
                "ingredient_id": self.ingredient_ids[0],  # Thịt bò
                "quantity": 500,
                "unit": "g",
                "expiry_date": (date.today() + timedelta(days=3)).isoformat()
            },
            {
                "user_id": self.user_ids[0],
                "ingredient_id": self.ingredient_ids[1],  # Cà chua
                "quantity": 5,
                "unit": "quả",
                "expiry_date": (date.today() + timedelta(days=7)).isoformat()
            }
        ]
        
        try:
            result = self.supabase.table("user_inventory").insert(inventory).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} inventory items")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 7: Meal Plans (→ user_profiles)
    # =========================================================================
    
    def insert_meal_plans(self):
        """Insert meal plans - Phụ thuộc user_profiles."""
        print("\n📅 BƯỚC 7: Inserting Meal Plans...")
        
        if not self.user_ids:
            print("   ⚠️ Skipped: No users found")
            return []
        
        today = date.today()
        meal_plans = [
            {
                "user_id": self.user_ids[0],
                "title": "Kế hoạch ăn tuần này",
                "description": "7 ngày ăn uống lành mạnh",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
                "status": "active",
                "nutrition_targets": {
                    "calories": 2000,
                    "protein": 150,
                    "carbs": 200,
                    "fat": 60
                },
                "preferences": {
                    "dietary_restrictions": [],
                    "allergies": [],
                    "cuisine_types": ["vietnamese"]
                }
            }
        ]
        
        try:
            result = self.supabase.table("meal_plans").insert(meal_plans).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            self.meal_plan_ids = [plan["id"] for plan in data]
            print(f"   ✅ Inserted {len(data)} meal plans")
            for plan in data:
                print(f"      → {plan['title']} ({plan['start_date']} to {plan['end_date']})")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 8: Meal Plan Meals (→ meal_plans, recipes)
    # =========================================================================
    
    def insert_meal_plan_meals(self):
        """Insert meal plan meals - Phụ thuộc meal_plans và recipes."""
        print("\n🍽️ BƯỚC 8: Inserting Meal Plan Meals...")
        
        if not self.meal_plan_ids or not self.recipe_ids:
            print("   ⚠️ Skipped: No meal plans or recipes found")
            return []
        
        today = date.today()
        meals = [
            {
                "meal_plan_id": self.meal_plan_ids[0],
                "recipe_id": self.recipe_ids[0],  # Phở Bò
                "date": today.isoformat(),
                "meal_type": "breakfast",
                "serving_size": 1.0,
                "is_completed": False
            },
            {
                "meal_plan_id": self.meal_plan_ids[0],
                "recipe_id": self.recipe_ids[1],  # Cơm Tấm
                "date": today.isoformat(),
                "meal_type": "lunch",
                "serving_size": 1.0,
                "is_completed": False
            }
        ]
        
        try:
            result = self.supabase.table("meal_plan_meals").insert(meals).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} meal plan meals")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 9: Shopping Lists (→ meal_plans, user_profiles)
    # =========================================================================
    
    def insert_shopping_lists(self):
        """Insert shopping lists - Phụ thuộc meal_plans và user_profiles."""
        print("\n🛒 BƯỚC 9: Inserting Shopping Lists...")
        
        if not self.meal_plan_ids or not self.user_ids:
            print("   ⚠️ Skipped: No meal plans or users found")
            return []
        
        shopping_lists = [
            {
                "meal_plan_id": self.meal_plan_ids[0],
                "user_id": self.user_ids[0],
                "title": "Đi chợ tuần này",
                "items": [
                    {
                        "ingredient_id": str(self.ingredient_ids[0]),
                        "name": "Thịt bò",
                        "quantity": 1000,
                        "unit": "g",
                        "is_checked": False
                    },
                    {
                        "ingredient_id": str(self.ingredient_ids[2]),
                        "name": "Gạo",
                        "quantity": 2,
                        "unit": "kg",
                        "is_checked": False
                    }
                ],
                "status": "pending"
            }
        ]
        
        try:
            result = self.supabase.table("shopping_lists").insert(shopping_lists).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} shopping lists")
            for sl in data:
                print(f"      → {sl['title']} ({len(sl['items'])} items)")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # BƯỚC 10: Daily Logs (→ user_profiles)
    # =========================================================================
    
    def insert_daily_logs(self):
        """Insert daily logs - Phụ thuộc user_profiles."""
        print("\n📊 BƯỚC 10: Inserting Daily Logs...")
        
        if not self.user_ids:
            print("   ⚠️ Skipped: No users found")
            return []
        
        logs = [
            {
                "user_id": self.user_ids[0],
                "date": date.today().isoformat(),
                "calories_consumed": 1800,
                "protein_consumed": 120,
                "carbs_consumed": 180,
                "fat_consumed": 50,
                "water_ml": 2000,
                "mood": "good",
                "energy_level": 8,
                "health_score": 85,
                "notes": "Ngày làm việc hiệu quả"
            }
        ]
        
        try:
            result = self.supabase.table("daily_logs").insert(logs).execute()
            data = cast(list[dict[str, Any]], result.data or [])
            print(f"   ✅ Inserted {len(data)} daily logs")
            return result.data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    # =========================================================================
    # MASTER FUNCTION: Chạy tất cả theo thứ tự
    # =========================================================================
    
    def insert_all(self):
        """Insert tất cả data theo đúng thứ tự dependency."""
        print("\n" + "="*60)
        print("🚀 BẮT ĐẦU INSERT DATA THEO THỨ TỰ")
        print("="*60)
        
        # Bước 1-3: Base tables (no dependencies)
        self.insert_user_profiles()
        self.insert_ingredients()
        self.insert_recipes()
        
        # Bước 4-6: First level dependencies
        self.insert_user_subscriptions()
        self.insert_recipe_ingredients()
        self.insert_user_inventory()
        
        # Bước 7: Meal plans (depends on users)
        self.insert_meal_plans()
        
        # Bước 8-10: Second level dependencies
        self.insert_meal_plan_meals()
        self.insert_shopping_lists()
        self.insert_daily_logs()
        
        print("\n" + "="*60)
        print("✅ HOÀN THÀNH! Đã insert tất cả data.")
        print("="*60)
        
        print("\n📊 Tổng kết:")
        print(f"   - Users: {len(self.user_ids)}")
        print(f"   - Ingredients: {len(self.ingredient_ids)}")
        print(f"   - Recipes: {len(self.recipe_ids)}")
        print(f"   - Meal Plans: {len(self.meal_plan_ids)}")
        
        print("\n💡 Kiểm tra data:")
        print("   python check_data.py")


def main():
    """Main function."""
    print("""
╔════════════════════════════════════════════════════════════╗
║  HƯỚNG DẪN INSERT DATA VÀO MENU GREEN DATABASE             ║
╚════════════════════════════════════════════════════════════╝

⚠️  QUAN TRỌNG: Trước khi chạy script này, hãy:

1. Đăng nhập Supabase Dashboard
2. Chạy schema_fixes.sql để fix:
   - RLS policies
   - Embedding dimension (768→3072)
   - Vector index

3. Sau đó chạy script này để insert data mẫu

Bạn có muốn tiếp tục? (y/n): """)
    
    choice = input().strip().lower()
    if choice != 'y':
        print("\n❌ Đã hủy.")
        return
    
    inserter = DataInserter()
    inserter.insert_all()


if __name__ == "__main__":
    main()
