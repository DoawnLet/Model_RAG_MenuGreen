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
        Create embedding vector for text using Google Gemini.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (768 dimensions for models/text-embedding-004)
        """
        embeddings = cls.get_google_embeddings()
        return await embeddings.aembed_query(text)
    
    @classmethod
    def get_user_profile(cls, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch user profile from Supabase.
        
        Returns None if user_id is invalid or profile not found.
        """
        try:
            # Validate UUID format
            import uuid
            uuid.UUID(user_id)
            
            client = cls.get_client()
            response = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
            return response.data if response.data else None  # type: ignore
        except (ValueError, Exception) as e:
            # Invalid UUID or query error - return None for graceful degradation
            logger.warning(f"Failed to fetch user profile for {user_id}: {e}")
            return None
    
    @classmethod
    def get_user_inventory(cls, user_id: str) -> list[dict[str, Any]]:
        """Fetch user's inventory items.
        
        Returns empty list if user_id is invalid or no inventory found.
        """
        try:
            # Validate UUID format
            import uuid
            uuid.UUID(user_id)
            
            client = cls.get_client()
            response = (
                client.table("user_inventory")
                .select("*, ingredients(name)")
                .eq("user_id", user_id)
                .execute()
            )
            return response.data or []  # type: ignore
        except (ValueError, Exception) as e:
            # Invalid UUID or query error - return empty list
            logger.warning(f"Failed to fetch inventory for {user_id}: {e}")
            return []
    
    @classmethod
    def get_user_subscription(cls, user_id: str) -> str:
        """
        Get user's subscription tier.
        In production, this would query Supabase Auth metadata.
        """
        # TODO: Implement actual subscription check
        # For now, return "free" as default
        return "free"
    
    # ========================================================================
    # Async versions for parallel execution (P0 Performance Optimization)
    # ========================================================================
    
    @classmethod
    async def get_user_profile_async(cls, user_id: str) -> Optional[dict[str, Any]]:
        """Async version: Fetch user profile from Supabase."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_profile, user_id)
    
    @classmethod
    async def get_user_inventory_async(cls, user_id: str) -> list[dict[str, Any]]:
        """Async version: Fetch user's inventory items."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_inventory, user_id)
    
    @classmethod
    async def get_user_subscription_async(cls, user_id: str) -> str:
        """Async version: Get user's subscription tier."""
        import asyncio
        return await asyncio.to_thread(cls.get_user_subscription, user_id)


# Convenience functions
def get_supabase() -> Client:
    """Get Supabase client instance."""
    return SupabaseClient.get_client()


async def create_embedding(text: str) -> list[float]:
    """Create embedding for text."""
    return await SupabaseClient.create_embedding(text)
