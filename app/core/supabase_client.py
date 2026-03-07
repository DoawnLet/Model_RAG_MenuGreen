"""
Supabase client wrapper for Menu Green.
Provides database access and embedding functions.
"""
import logging
from typing import Optional, Any
from supabase import create_client, Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Wrapper for Supabase operations.
    """
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance."""
        if cls._instance is None:
            settings = get_settings()
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_key,
            )
        return cls._instance
    
    @classmethod
    def get_google_embeddings(cls):
        """Get or create Google Generative AI Embeddings client."""
        # We import here to avoid circular imports or if package is missing
        from langchain_google_genai import GoogleGenerativeAIEmbeddings  # type: ignore
        
        settings = get_settings()
        from pydantic import SecretStr
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            api_key=SecretStr(settings.google_api_key) if settings.google_api_key else None,
        )

    @classmethod
    async def create_embedding(cls, text: str) -> list[float]:
        """
        Create embedding vector for text.
        Priority: ONNX local (BAAI/bge-m3) → Gemini API fallback.
        """
        try:
            from app.core.embedding_onnx import get_embedding
            return await get_embedding(text)
        except Exception as e:
            logger.warning(f"ONNX embedding failed, using Gemini: {e}")
            return await cls.create_embedding_gemini(text)

    @classmethod
    async def create_embedding_gemini(cls, text: str) -> list[float]:
        """
        Create embedding via Gemini API (fallback).
        """
        embeddings = cls.get_google_embeddings()
        return await embeddings.aembed_query(text)
    
    @classmethod
    def get_user_profile(cls, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch user profile from Supabase."""
        try:
            import uuid
            uuid.UUID(user_id)
            client = cls.get_client()
            response = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
            return response.data if response.data else None  # type: ignore
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to fetch user profile for {user_id}: {e}")
            return None

    @classmethod
    def upsert_user_profile(cls, user_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Upsert user profile (insert or update).
        Dùng cho onboarding form.
        """
        try:
            client = cls.get_client()
            payload = {"id": user_id, **data}
            response = (
                client.table("user_profiles")
                .upsert(payload, on_conflict="id")
                .execute()
            )
            return response.data[0] if response.data else None  # type: ignore
        except Exception as e:
            logger.error(f"Failed to upsert user profile for {user_id}: {e}")
            raise

    @classmethod
    def get_user_inventory(cls, user_id: str) -> list[dict[str, Any]]:
        """Fetch user's inventory items with ingredient names."""
        try:
            import uuid
            uuid.UUID(user_id)
            client = cls.get_client()
            response = (
                client.table("user_inventory")
                .select("*, ingredients(name, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g)")
                .eq("user_id", user_id)
                .execute()
            )
            return response.data or []  # type: ignore
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to fetch inventory for {user_id}: {e}")
            return []

    @classmethod
    def upsert_user_inventory(cls, user_id: str, items: list[dict[str, Any]]) -> bool:
        """
        Bulk upsert user inventory items.
        items: [{"name": "cà chua", "quantity": 500, "unit": "g", "expiry_date": "2026-03-15"}, ...]
        
        - Tìm ingredient_id theo tên trong bảng ingredients
        - Nếu chưa có ingredient → tạo mới
        - Upsert vào user_inventory
        """
        try:
            client = cls.get_client()
            upserted = []

            for item in items:
                ingredient_name = item.get("name", "").strip()
                if not ingredient_name:
                    continue

                # 1. Tìm ingredient theo tên
                ing_res = (
                    client.table("ingredients")
                    .select("id")
                    .ilike("name", ingredient_name)
                    .limit(1)
                    .execute()
                )

                if ing_res.data:
                    ingredient_id = ing_res.data[0]["id"]
                else:
                    # 2. Tạo ingredient mới nếu chưa có
                    new_ing = client.table("ingredients").insert({
                        "name": ingredient_name,
                        "calories_per_100g": item.get("calories_per_100g", 0),
                        "protein_per_100g": item.get("protein_per_100g", 0),
                        "carbs_per_100g": item.get("carbs_per_100g", 0),
                        "fat_per_100g": item.get("fat_per_100g", 0),
                        "category": item.get("category", "other"),
                    }).execute()
                    ingredient_id = new_ing.data[0]["id"]

                # 3. Upsert vào user_inventory
                upserted.append({
                    "user_id": user_id,
                    "ingredient_id": ingredient_id,
                    "quantity": item.get("quantity", 0),
                    "unit": item.get("unit", "g"),
                    "expiry_date": item.get("expiry_date"),
                })

            if upserted:
                client.table("user_inventory").upsert(
                    upserted, on_conflict="user_id,ingredient_id"
                ).execute()

            logger.info(f"✅ Upserted {len(upserted)} inventory items for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to upsert inventory for {user_id}: {e}")
            raise

    @classmethod
    def get_recipe_calories_by_name(cls, dish_name: str) -> Optional[dict[str, Any]]:
        """
        Tra cứu calo của món ăn theo tên trong DB.
        Returns: {calories, protein, carbs, fat, recipe_name} hoặc None
        """
        try:
            client = cls.get_client()
            result = (
                client.table("recipes")
                .select("name, calories_per_serving, protein_per_serving, carbs_per_serving, fat_per_serving")
                .ilike("name", f"%{dish_name}%")
                .limit(1)
                .execute()
            )
            if result.data and result.data[0].get("calories_per_serving"):
                r = result.data[0]
                return {
                    "recipe_name": r["name"],
                    "calories": r["calories_per_serving"],
                    "protein": r.get("protein_per_serving", 0),
                    "carbs": r.get("carbs_per_serving", 0),
                    "fat": r.get("fat_per_serving", 0),
                }
        except Exception as e:
            logger.warning(f"DB calorie lookup failed for '{dish_name}': {e}")
        return None

    @classmethod
    def get_user_subscription(cls, user_id: str) -> str:
        """Get user's subscription tier from Supabase."""
        try:
            import uuid
            uuid.UUID(user_id)
            client = cls.get_client()
            response = (
                client.table("user_subscriptions")
                .select("tier")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .single()
                .execute()
            )
            if response.data:
                return response.data.get("tier", "free")  # type: ignore
        except Exception as e:
            logger.warning(f"Failed to fetch subscription for {user_id}: {e}")
        return "free"

    # ========================================================================
    # Async versions
    # ========================================================================

    @classmethod
    async def get_user_profile_async(cls, user_id: str) -> Optional[dict[str, Any]]:
        """Async: Fetch user profile."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_profile, user_id)

    @classmethod
    async def get_user_inventory_async(cls, user_id: str) -> list[dict[str, Any]]:
        """Async: Fetch user inventory."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_inventory, user_id)

    @classmethod
    async def get_user_subscription_async(cls, user_id: str) -> str:
        """Async: Get subscription tier."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_subscription, user_id)

    @classmethod
    async def upsert_user_profile_async(cls, user_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Async: Upsert user profile."""
        import asyncio
        return await asyncio.to_thread(cls.upsert_user_profile, user_id, data)

    @classmethod
    async def upsert_user_inventory_async(cls, user_id: str, items: list[dict[str, Any]]) -> bool:
        """Async: Upsert user inventory."""
        import asyncio
        return await asyncio.to_thread(cls.upsert_user_inventory, user_id, items)


# Convenience functions
def get_supabase() -> Client:
    """Get Supabase client instance."""
    return SupabaseClient.get_client()


async def create_embedding(text: str) -> list[float]:
    """Create embedding for text (ONNX → Gemini fallback)."""
    return await SupabaseClient.create_embedding(text)
