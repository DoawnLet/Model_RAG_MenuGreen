"""
Configuration management for Menu Green.
Loads environment variables from .env file.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    
    # Google Gemini
    google_api_key: str = ""
    llm_model: str = "gemini-2.0-flash-001"
    embedding_model: str = "models/text-embedding-004"
    
    # App
    app_name: str = "Menu Green"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
