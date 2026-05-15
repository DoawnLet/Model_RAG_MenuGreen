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
    postgres_url: str = ""  # Direct connection string for LangGraph checkpointing

    # Google Gemini
    google_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = "models/gemini-embedding-001"

    # App
    app_name: str = "Menu Green"
    debug: bool = False
    serve_frontend: bool = False
    enable_training_endpoint: bool = False
    worker_timeout_seconds: float = 120.0
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    enable_review_queue: bool = True
    review_queue_path: str = "training/review_queue.jsonl"
    intent_confidence_threshold: float = 0.55

    # Auto-Discovery Agent
    discovery_delay_seconds: float = 2.0
    discovery_max_per_run: int = 20
    jina_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
