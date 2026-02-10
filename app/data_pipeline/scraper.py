"""
Web Scraper for Vietnamese Recipe Sites.
Demonstrates scraping from Cookpad VN or similar sites.
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from pydantic import BaseModel


class RawRecipe(BaseModel):
    """Raw scraped recipe data (unstructured)."""
    source_url: str
    title: str
    raw_ingredients: str  # Raw text, not parsed
    raw_instructions: str
    image_url: Optional[str] = None


class RecipeScraper:
    """
    Simple scraper for recipe websites.
    Note: Always respect robots.txt and rate limits!
    """
    
    def __init__(self, delay_seconds: float = 1.0):
        self.delay = delay_seconds
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def scrape_cookpad_recipe(self, url: str) -> Optional[RawRecipe]:
        """
        Scrape a single recipe from Cookpad VN.
        
        Args:
            url: Recipe URL
            
        Returns:
            RawRecipe or None if failed
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract title
            title_elem = soup.select_one("h1.recipe-title, h1[class*='title']")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Extract ingredients (usually in a list)
            ingredients_elem = soup.select("div.ingredient-list li, [class*='ingredient'] li")
            raw_ingredients = "\n".join([li.get_text(strip=True) for li in ingredients_elem])
            
            # Extract instructions
            instructions_elem = soup.select("div.step-text, [class*='instruction'] li, [class*='step'] p")
            raw_instructions = "\n".join([step.get_text(strip=True) for step in instructions_elem])
            
            # Extract image
            image_elem = soup.select_one("img.recipe-image, [class*='recipe'] img")
            image_url = image_elem.get("src") if image_elem else None
            
            return RawRecipe(
                source_url=url,
                title=title,
                raw_ingredients=raw_ingredients or "No ingredients found",
                raw_instructions=raw_instructions or "No instructions found",
                image_url=image_url,
            )
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return None
    
    async def scrape_multiple(self, urls: list[str]) -> list[RawRecipe]:
        """
        Scrape multiple URLs with rate limiting.
        
        Args:
            urls: List of recipe URLs
            
        Returns:
            List of successfully scraped recipes
        """
        recipes = []
        
        for i, url in enumerate(urls):
            print(f"📥 Scraping {i+1}/{len(urls)}: {url[:50]}...")
            recipe = await self.scrape_cookpad_recipe(url)
            
            if recipe:
                recipes.append(recipe)
                print(f"   ✅ Got: {recipe.title}")
            
            # Rate limiting
            if i < len(urls) - 1:
                await asyncio.sleep(self.delay)
        
        return recipes


# ============================================================================
# Alternative: Generate Synthetic Vietnamese Recipes with LLM
# ============================================================================

SYNTHETIC_PROMPT = """
Bạn là chuyên gia ẩm thực Việt Nam. Hãy tạo ra {count} công thức món ăn Việt Nam 
theo format JSON sau. Mỗi món phải thực tế, ngon miệng và có thể nấu tại nhà.

Yêu cầu:
- Đa dạng: phở, bún, cơm, xào, canh, gỏi...
- Bao gồm món cho: gymer (giàu đạm), văn phòng (nhanh gọn), gia đình
- Mỗi món có đầy đủ: tên, nguyên liệu, cách làm, thời gian

Output format (JSON array):
[
  {{
    "name": "Tên món",
    "description": "Mô tả ngắn",
    "ingredients": ["nguyên liệu 1", "nguyên liệu 2"],
    "instructions": "Bước 1... Bước 2...",
    "prep_time_minutes": 10,
    "cook_time_minutes": 20,
    "servings": 2,
    "tags": ["tag1", "tag2"],
    "macros_estimate": {{"protein_g": 30, "carbs_g": 40, "fat_g": 10}}
  }}
]

Tạo {count} món:
"""


async def generate_synthetic_recipes(count: int = 10, category: str = None) -> list[dict]:
    """
    Generate synthetic Vietnamese recipes using Google Gemini.
    
    Args:
        count: Number of recipes to generate
        category: Optional cuisine category to focus on (e.g. "Món canh", "Món chay")
        
    Returns:
        List of recipe dictionaries
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import SystemMessage, HumanMessage
    from app.core.config import get_settings
    import json
    
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=0.9, # Higher temperature for variety
    )
    
    prompt_text = SYNTHETIC_PROMPT.format(count=count)
    if category:
        prompt_text += f"\n\n👉 CHỦ ĐỀ SÁNG TẠO: Hãy tập trung vào các món thuộc nhóm '{category}'. Đảm bảo không trùng lặp."
    
    print(f"🤖 Generating {count} synthetic recipes (Category: {category or 'General'})...")
    
    response = await llm.ainvoke([
        SystemMessage(content="You are a Vietnamese cuisine expert. Output valid JSON only."),
        HumanMessage(content=prompt_text),
    ])
    
    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        # Handle both {"recipes": [...]} and [...] formats
        recipes = result.get("recipes", result) if isinstance(result, dict) else result
        print(f"✅ Generated {len(recipes)} recipes")
        return recipes
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response: {e}")
        return []


# ============================================================================
# Demo Usage
# ============================================================================

async def demo():
    """Demo the scraper and synthetic generator."""
    
    # Option 1: Scrape (requires valid URLs)
    # scraper = RecipeScraper(delay_seconds=1.5)
    # urls = ["https://cookpad.com/vn/cong-thuc/123456"]
    # recipes = await scraper.scrape_multiple(urls)
    
    # Option 2: Generate synthetic data
    recipes = await generate_synthetic_recipes(count=5)
    
    for r in recipes:
        print(f"\n📝 {r.get('name', 'Unknown')}")
        print(f"   Ingredients: {', '.join(r.get('ingredients', [])[:3])}...")
        print(f"   Tags: {r.get('tags', [])}")


if __name__ == "__main__":
    asyncio.run(demo())
