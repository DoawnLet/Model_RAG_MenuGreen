"""
LLM Data Cleaner - Converts raw recipe text to structured JSON.
Uses GPT-4o-mini for cost-effective normalization.
"""
import asyncio
import json
from typing import Optional
from pydantic import BaseModel


from app.core.config import get_settings
from app.data_pipeline.scraper import RawRecipe


class CleanedRecipe(BaseModel):
    """Structured recipe ready for database insertion."""
    name: str
    description: str
    ingredients: list[str]
    instructions: str
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    tags: list[str] = []
    nutrients: Optional[dict] = None  # {"calories": X, "protein": Y, "carbs": Z, "fat": W}
    vector_text: str  # Text optimized for embedding


CLEANING_PROMPT = """
Bạn là chuyên gia dinh dưỡng và khoa học dữ liệu. Nhiệm vụ: Chuyển đổi công thức thô sang JSON chuẩn và GẮN NHÃN NGỮ CẢNH (Contextual Tagging).

**Công thức thô:**
Tiêu đề: {title}
Nguyên liệu: {raw_ingredients}
Cách làm: {raw_instructions}

**Yêu cầu xử lý:**
1. **Chuẩn hóa:** Tách số lượng, đơn vị, tên nguyên liệu (VD: "2 quả trứng" -> "2", "quả", "trứng").
2. **Ước tính Macro:** Tính Calo, Protein, Carbs, Fat (nếu chưa có).
3. **Gắn Tag Ngữ Cảnh (QUAN TRỌNG):**
   - Dựa vào thành phần và thời gian, hãy gắn các tag sau (nếu phù hợp):
     - `#no-sleepy`: Ít tinh bột, nhiều rau/đạm (tránh buồn ngủ sau ăn).
     - `#quick-lunch`: Tổng thời gian < 15 phút.
     - `#high-protein`: Giàu đạm (>30g/khẩu phần) -> cho gymer.
     - `#pre-workout`: Nhiều carbs dễ tiêu, ít chất béo.
     - `#warming`: Món nóng, cay, nhiều gia vị ấm (gừng, tiêu) -> cho ngày mưa/lạnh.
     - `#cooling`: Món thanh mát, luộc, canh, gỏi -> cho ngày hè.
     - `#office-friendly`: Gọn nhẹ, ít mùi nồng.
4. **Vector Text:** Viết mô tả ngắn gọn chứa tên món, nguyên liệu chính và các tag trên để tối ưu cho tìm kiếm vector.

**Output JSON:**
{{
  "name": "Tên món chuẩn",
  "description": "Mô tả hấp dẫn 1-2 câu",
  "ingredients": ["nguyên liệu 1", "nguyên liệu 2"],
  "nutrients": {{"calories": 500, "protein": 30, "carbs": 40, "fat": 10}}, 
  "instructions": "Cách làm...",
  "prep_time_minutes": 10,
  "cook_time_minutes": 5,
  "tags": ["#quick-lunch", "#no-sleepy", "#office-friendly"],
  "vector_text": "Salad ức gà áp chảo sốt chanh leo #high-protein #quick-lunch văn phòng ít béo"
}}

Chỉ trả về JSON hợp lệ.
"""


class RecipeCleaner:
    """
    Uses LLM to clean and structure raw recipe data.
    """
    
    def __init__(self):
        from langchain_google_genai import ChatGoogleGenerativeAI
        settings = get_settings()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0.3,
        )
    
    async def clean_recipe(self, raw: RawRecipe) -> Optional[CleanedRecipe]:
        """
        Clean a single raw recipe using LLM.
        
        Args:
            raw: RawRecipe from scraper
            
        Returns:
            CleanedRecipe or None if failed
        """
        prompt = CLEANING_PROMPT.format(
            title=raw.title,
            raw_ingredients=raw.raw_ingredients,
            raw_instructions=raw.raw_instructions,
        )
        
        try:
            # Gemini isn't strict on response_format="json_object" in langchain yet without structured output
            # But we can just ask for JSON in system prompt (already there).
            # We can use JsonOutputParser if we want to be fancy, but simple json.loads is fine for now.
            
            from langchain_core.messages import SystemMessage, HumanMessage
            
            response = await self.llm.ainvoke([
                SystemMessage(content="You output valid JSON only."),
                HumanMessage(content=prompt),
            ])
            
            # Type guard for response.content
            if not isinstance(response.content, str):
                print(f"❌ LLM returned non-string content for '{raw.title}'")
                return None
            
            # Clean up potential markdown code blocks ```json ... ```
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return CleanedRecipe(**data)
            
        except Exception as e:
            print(f"❌ Failed to clean recipe '{raw.title}': {e}")
            return None
    
    async def clean_batch(
        self, 
        raw_recipes: list[RawRecipe],
        concurrency: int = 3,
    ) -> list[CleanedRecipe]:
        """
        Clean multiple recipes with controlled concurrency.
        
        Args:
            raw_recipes: List of raw recipes
            concurrency: Max parallel API calls
            
        Returns:
            List of cleaned recipes
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def clean_with_limit(raw: RawRecipe) -> Optional[CleanedRecipe]:
            async with semaphore:
                print(f"🧹 Cleaning: {raw.title}...")
                result = await self.clean_recipe(raw)
                if result:
                    print(f"   ✅ Done: {result.name}")
                return result
        
        tasks = [clean_with_limit(r) for r in raw_recipes]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]


# ============================================================================
# Full Pipeline: Clean -> Vectorize -> Store
# ============================================================================

async def process_and_store(cleaned_recipes: list[CleanedRecipe]):
    """
    Generate embeddings and store recipes in Supabase.
    
    Args:
        cleaned_recipes: List of cleaned recipes to store
    """
    from app.core.supabase_client import SupabaseClient
    
    client = SupabaseClient.get_client()
    
    for recipe in cleaned_recipes:
        print(f"📦 Processing: {recipe.name}")
        
        # Generate embedding from vector_text
        embedding = await SupabaseClient.create_embedding(recipe.vector_text)
        
        # Prepare data for insertion
        data = {
            "name": recipe.name,
            "description": recipe.description,
            "instructions": recipe.instructions,
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "servings": recipe.servings,
            "embedding": embedding,
        }
        
        # Upsert to avoid duplicates
        try:
            existing = client.table("recipes").select("id").eq("name", recipe.name).execute()
            
            if existing.data:
                # Update existing
                client.table("recipes").update(data).eq("name", recipe.name).execute()
                print(f"   🔄 Updated: {recipe.name}")
            else:
                # Insert new
                client.table("recipes").insert(data).execute()
                print(f"   ✅ Inserted: {recipe.name}")
                
        except Exception as e:
            print(f"   ❌ Error storing {recipe.name}: {e}")
    
    print(f"\n🎉 Processed {len(cleaned_recipes)} recipes!")


# ============================================================================
# Demo
# ============================================================================

async def demo():
    """Demo the cleaning pipeline."""
    from app.data_pipeline.scraper import RawRecipe
    
    # Simulate raw scraped data
    raw_samples = [
        RawRecipe(
            source_url="https://example.com/1",
            title="Canh chua cá lóc",
            raw_ingredients="""
            - 500g cá lóc
            - 2 quả cà chua
            - 1 nắm rau om
            - Me chua, đường, nước mắm
            - Giá đỗ, đậu bắp
            """,
            raw_instructions="""
            Sơ chế cá, nấu nước dùng với me. Cho cà chua vào, 
            thêm cá nấu chín. Nêm nếm, thêm rau thơm.
            """,
        ),
        RawRecipe(
            source_url="https://example.com/2",
            title="Thịt kho tàu",
            raw_ingredients="""
            - 1kg thịt ba chỉ
            - 10 quả trứng luộc
            - Nước dừa tươi
            - Nước mắm, đường thắng caramel
            """,
            raw_instructions="""
            Thắng đường caramen, cho thịt vào xào. Đổ nước dừa ngập thịt.
            Kho liu riu 2 tiếng. Cho trứng vào 30 phút cuối.
            """,
        ),
    ]
    
    # Clean with LLM
    cleaner = RecipeCleaner()
    cleaned = await cleaner.clean_batch(raw_samples)
    
    for c in cleaned:
        print(f"\n📝 {c.name}")
        print(f"   Tags: {c.tags}")
        print(f"   Nutrients: {c.nutrients}")
        print(f"   Vector: {c.vector_text[:80]}...")


if __name__ == "__main__":
    asyncio.run(demo())
