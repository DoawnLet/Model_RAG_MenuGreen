"""
RAG Tool - Recipe search using pgvector similarity.
Queries Supabase to find recipes based on user-provided ingredients.
"""

from typing import Optional, Any, cast
from pydantic import BaseModel
from supabase import Client


class RecipeMatch(BaseModel):
    """A recipe matched from vector search."""

    id: str
    name: str
    description: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    similarity_score: float


class RAGTool:
    """
    Recipe retrieval tool using pgvector for semantic search.
    """

    def __init__(self, supabase_client: Client, embedding_func):
        """
        Initialize RAG tool.

        Args:
            supabase_client: Supabase client instance
            embedding_func: Function that converts text to embedding vector
        """
        self.client = supabase_client
        self.embed = embedding_func

    async def search_recipes_by_ingredients(
        self,
        ingredients: list[str],
        limit: int = 5,
        user_id: Optional[str] = None,
        dietary_restrictions: Optional[list[str]] = None,
    ) -> list[RecipeMatch]:
        """
        Search for recipes that match the given ingredients.

        P1 Feature: Added dietary_restrictions filtering.

        This function:
        1. Converts ingredient list to a query string
        2. Generates embedding vector using Google Gemini
        3. Queries pgvector for similar recipes
        4. Filters by dietary restrictions if provided
        5. Returns top matches

        Args:
            ingredients: List of ingredient names (e.g., ["chicken", "broccoli"])
            limit: Maximum number of results
            user_id: Optional user ID for personalization
            dietary_restrictions: Optional list of dietary tags to filter

        Returns:
            List of matching recipes sorted by similarity
        """
        # Create query text from ingredients
        query_text = ", ".join(ingredients)
        query_text = f"Món ăn với nguyên liệu: {query_text}"

        # Generate embedding
        query_embedding = await self.embed(query_text)

        # Query pgvector using Supabase RPC
        # P1 Feature: Fetch more if filtering is needed
        response = self.client.rpc(
            "match_recipes",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.5,
                "match_count": limit * 2 if dietary_restrictions else limit,
            },
        ).execute()

        if not response.data or not isinstance(response.data, list):
            return []

        # Cast to list[dict] for type safety
        results = cast(list[dict[str, Any]], response.data)

        # P1 Feature: Filter by dietary restrictions if provided
        if dietary_restrictions:
            filtered_results = []
            for row in results:
                recipe_tags = row.get("dietary_tags", [])
                if recipe_tags and isinstance(recipe_tags, list):
                    if all(tag in recipe_tags for tag in dietary_restrictions):
                        filtered_results.append(row)
                elif not recipe_tags:
                    filtered_results.append(row)

            results = filtered_results[:limit]

        return [
            RecipeMatch(
                id=row["id"],
                name=row["name"],
                description=row.get("description"),
                prep_time_minutes=row.get("prep_time_minutes"),
                cook_time_minutes=row.get("cook_time_minutes"),
                servings=row.get("servings"),
                similarity_score=row.get("similarity", 0.0),
            )
            for row in results
        ]

    async def search_by_text(
        self,
        query: str,
        limit: int = 5,
        dietary_restrictions: Optional[list[str]] = None,
    ) -> list[RecipeMatch]:
        """
        Search recipes by free-text query.

        P1 Feature: Added dietary_restrictions filtering.

        Args:
            query: Natural language query
            limit: Maximum results
            dietary_restrictions: Optional list of dietary tags to filter
                                (e.g., ['vegetarian', 'gluten_free', 'halal'])

        Returns:
            List of matching recipes
        """
        query_embedding = await self.embed(query)

        # P1 Feature: Add dietary filtering if provided
        rpc_params = {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": limit * 2
            if dietary_restrictions
            else limit,  # Fetch more for filtering
        }

        response = self.client.rpc("match_recipes", rpc_params).execute()

        if not response.data or not isinstance(response.data, list):
            return []

        # Cast to list[dict] for type safety
        results = cast(list[dict[str, Any]], response.data)

        # P1 Feature: Filter by dietary restrictions if provided
        if dietary_restrictions:
            filtered_results = []
            for row in results:
                # Check if recipe has dietary_tags field (may not exist in old schema)
                recipe_tags = row.get("dietary_tags", [])
                if recipe_tags and isinstance(recipe_tags, list):
                    # Check if all required restrictions are satisfied
                    if all(tag in recipe_tags for tag in dietary_restrictions):
                        filtered_results.append(row)
                # If no dietary_tags field exists, include all recipes (backward compatible)
                elif not recipe_tags:
                    filtered_results.append(row)

            results = filtered_results[:limit]  # Limit after filtering

        return [
            RecipeMatch(
                id=row["id"],
                name=row["name"],
                description=row.get("description"),
                prep_time_minutes=row.get("prep_time_minutes"),
                cook_time_minutes=row.get("cook_time_minutes"),
                servings=row.get("servings"),
                similarity_score=row.get("similarity", 0.0),
            )
            for row in results
        ]


def format_recipe_results(recipes: list[RecipeMatch]) -> str:
    """
    Format recipe search results for display.

    Args:
        recipes: List of matched recipes

    Returns:
        Formatted string
    """
    if not recipes:
        return "❌ Không tìm thấy công thức phù hợp với nguyên liệu của bạn."

    lines = ["🍳 **Công thức được đề xuất:**\n"]

    for i, recipe in enumerate(recipes, 1):
        total_time = (recipe.prep_time_minutes or 0) + (recipe.cook_time_minutes or 0)
        time_str = f"{total_time} phút" if total_time else "N/A"

        lines.append(f"**{i}. {recipe.name}**")
        if recipe.description:
            lines.append(f"   {recipe.description[:100]}...")
        lines.append(
            f"   ⏱️ Thời gian: {time_str} | 🍽️ Khẩu phần: {recipe.servings or 'N/A'}"
        )
        lines.append("")

    return "\n".join(lines)
