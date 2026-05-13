import hashlib
import time
from typing import Optional
from app.core.config import get_settings


class MemoryManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Lazy import to avoid circular dependencies or import-time crashes
        from mem0 import Memory

        # Memory cache with TTL (P1 Performance Optimization)
        self._cache = {}  # {cache_key: (result, timestamp)}
        self._cache_ttl = 300  # 5 minutes TTL

        settings = get_settings()

        config = {
            "llm": {
                "provider": "gemini",
                "config": {
                    "model": settings.llm_model,
                    "api_key": settings.google_api_key,
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": settings.embedding_model,
                    "api_key": settings.google_api_key,
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "menu_green_memories",
                    "path": "./mem0_chroma_db",
                },
            },
            "history_db_path": "./mem0_history.db",
        }

        # Initialize Mem0
        self.memory = Memory.from_config(config)

    def add_memory(self, user_id: str, text: str):
        """Add a new memory for the user."""
        return self.memory.add(text, user_id=user_id)

    def get_memories(self, user_id: str, query: Optional[str] = None):
        """Retrieve relevant memories."""
        if query:
            return self.memory.search(query, filters={"user_id": user_id})
        else:
            return self.memory.get_all(filters={"user_id": user_id})

    def get_formatted_context(self, user_id: str, query: str) -> str:
        """Get memories formatted as a string for LLM context.

        P1 Optimization: Cached with 5 minute TTL to reduce ChromaDB latency.
        P2 Observability: Tracks cache hits/misses.
        """
        from app.core.metrics import (
            record_cache_hit,
            record_cache_miss,
            update_cache_size,
        )

        # Generate cache key from user_id and query
        cache_key = f"{user_id}:{hashlib.md5(query.encode()).hexdigest()[:8]}"
        current_time = time.time()

        # Check cache
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if current_time - timestamp < self._cache_ttl:
                record_cache_hit()  # P2 Observability
                return cached_result
            else:
                # Expired, remove from cache
                del self._cache[cache_key]

        # Cache miss
        record_cache_miss()  # P2 Observability
        memories = self.search_memories(user_id, query)
        if not memories:
            result = ""
            self._cache[cache_key] = (result, current_time)
            return result

        # Handle different return formats from Mem0/ChromaDB
        formatted_list = []

        # If it's a dict wrapper (e.g. {'results': [...]})
        if isinstance(memories, dict):
            memories = (
                memories.get("results", [])
                or memories.get("memories", [])
                or [memories]
            )

        # Use robust iteration
        if isinstance(memories, list):
            for m in memories:
                if isinstance(m, dict):
                    formatted_list.append(f"- {m.get('memory', str(m))}")
                elif isinstance(m, str):
                    formatted_list.append(f"- {m}")
                else:
                    formatted_list.append(f"- {str(m)}")

        context_str = "\n".join(formatted_list)
        result = f"\n\nTHÔNG TIN ĐÃ BIẾT VỀ USER:\n{context_str}\n"

        # Store in cache with timestamp
        self._cache[cache_key] = (result, current_time)

        # Cleanup old cache entries and update metrics (P2 Observability)
        if len(self._cache) > 100:  # Keep max 100 entries
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        update_cache_size(len(self._cache))  # P2 Observability

        return result

    def search_memories(self, user_id: str, query: str):
        """Wrapper for search to be safe."""
        results = self.memory.search(query, filters={"user_id": user_id})
        # Mem0 returns a list of dictionaries.
        # Structure usually: [{'memory': '...', 'score': ...}, ...]
        return results

    def search(self, query: str, user_id: str):
        """Direct wrapper for Mem0 search."""
        return self.memory.search(query, filters={"user_id": user_id})


# Singleton accessor
def get_memory_manager():
    return MemoryManager()
