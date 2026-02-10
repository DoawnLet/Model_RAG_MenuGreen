"""
Supabase client wrapper for Menu Green.
Provides database access and embedding functions.
"""
from typing import Optional
from supabase import create_client, Client
from supabase import create_client, Client

from app.core.config import get_settings


class SupabaseClient:
    """
    Wrapper for Supabase operations.
    """
    
    _instance: Optional[Client] = None
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
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        
        settings = get_settings()
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key,
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
    def get_user_profile(cls, user_id: str) -> Optional[dict]:
        """Fetch user profile from Supabase."""
        client = cls.get_client()
        
        response = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        
        return response.data if response.data else None
    
    @classmethod
    def get_user_inventory(cls, user_id: str) -> list[dict]:
        """Fetch user's inventory items."""
        client = cls.get_client()
        
        response = (
            client.table("user_inventory")
            .select("*, ingredients(name)")
            .eq("user_id", user_id)
            .execute()
        )
        
        return response.data or []
    
    @classmethod
    def get_user_subscription(cls, user_id: str) -> str:
        """
        Get user's subscription tier.
        In production, this would query Supabase Auth metadata.
        """
        # TODO: Implement actual subscription check
        # For now, return "free" as default
        return "free"


# Convenience functions
def get_supabase() -> Client:
    """Get Supabase client instance."""
    return SupabaseClient.get_client()


async def create_embedding(text: str) -> list[float]:
    """Create embedding for text."""
    return await SupabaseClient.create_embedding(text)
