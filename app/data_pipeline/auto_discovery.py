"""
Auto-Discovery Agent — Tự động cào công thức nấu ăn từ các website Việt Nam.

Pipeline:
1. Discover: Tìm link công thức mới từ website mục tiêu (Jina Search)
2. Crawl: Đọc nội dung trang web (Jina Reader via WebBrowserTool)
3. Extract: Trích xuất cấu trúc bằng LLM (Gemini → CleanedRecipe)
4. Dedup: Kiểm tra trùng lặp trong Supabase
5. Store: Lưu trữ + tạo vector embedding

Usage:
    agent = AutoDiscoveryAgent()
    result = await agent.run(max_recipes=10)
"""
import asyncio
import logging
import re
import httpx
from typing import Optional
from datetime import datetime

from app.agents.web_browser import WebBrowserTool
from app.data_pipeline.cleaner import CleanedRecipe, process_and_store
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


# ============================================================================
# Site Configurations
# ============================================================================

# URL patterns that indicate listing/category pages (NOT individual recipes)
SKIP_URL_PATTERNS = [
    r"/tag/",
    r"/category/",
    r"/recipe-type/",
    r"/page/\d+",
    r"/muc-luc",
    r"/\d{4}/\d{2}/$",  # Date archive pages like /2019/02/
]

SITE_CONFIGS = {
    "cooky": {
        "name": "Cooky.vn",
        "search_queries": [
            "site:cooky.vn công thức món ăn mới",
            "site:cooky.vn cách nấu món Việt",
            "site:cooky.vn món ngon mỗi ngày",
            "site:cooky.vn món ăn healthy giảm cân",
            "site:cooky.vn món ăn nhanh văn phòng",
        ],
        "url_pattern": r"cooky\.vn/",  # Relaxed pattern to match more Cooky URLs
    },
    "savoury": {
        "name": "SavouryDays",
        "search_queries": [
            "site:savourydays.com công thức nấu ăn",
            "site:savourydays.com món Việt Nam",
            "site:savourydays.com bữa ăn healthy",
        ],
        "url_pattern": r"savourydays\.com/",
    },
    "cookpad": {
        "name": "Cookpad VN",
        "search_queries": [
            "site:cookpad.com/vn công thức Việt Nam",
            "site:cookpad.com/vn món ăn đơn giản",
        ],
        "url_pattern": r"cookpad\.com/vn/",
    },
}


# ============================================================================
# Extraction Prompt
# ============================================================================

EXTRACTION_PROMPT = """
Bạn là chuyên gia ẩm thực Việt Nam kiêm chuyên gia dinh dưỡng. 
Nhiệm vụ: Đọc nội dung trang web dưới đây và trích xuất thông tin công thức nấu ăn.

**Nội dung trang web (Markdown):**
{content}

**Yêu cầu:**
1. Trích xuất: tên món, mô tả, danh sách nguyên liệu, cách làm, thời gian nấu
2. Ước tính dinh dưỡng: calories, protein, carbs, fat (mỗi khẩu phần)
3. Gắn tag ngữ cảnh:
   - `#high-protein`: Giàu đạm (>30g/khẩu phần)
   - `#quick-lunch`: Tổng thời gian < 15 phút
   - `#no-sleepy`: Ít tinh bột, tránh buồn ngủ
   - `#office-friendly`: Gọn nhẹ, ít mùi
   - `#warming`: Món nóng, cay, ấm
   - `#cooling`: Món thanh mát
   - `#pre-workout`: Nhiều carbs dễ tiêu
4. Tạo vector_text: mô tả ngắn gọn chứa tên + nguyên liệu chính + tags

**Output JSON (ONLY valid JSON, no explanation):**
{{
  "name": "Tên món",
  "description": "Mô tả hấp dẫn 1-2 câu",
  "ingredients": ["nguyên liệu 1", "nguyên liệu 2"],
  "instructions": "Bước 1:... Bước 2:...",
  "prep_time_minutes": 10,
  "cook_time_minutes": 20,
  "servings": 2,
  "tags": ["#high-protein", "#warming"],
  "nutrients": {{"calories": 450, "protein_g": 30, "carbs_g": 50, "fat_g": 15}},
  "vector_text": "Tên món + nguyên liệu chính + tags"
}}

Nếu trang web KHÔNG chứa công thức nấu ăn, trả về: {{"error": "not_a_recipe"}}
"""


# ============================================================================
# Auto-Discovery Agent
# ============================================================================

class AutoDiscoveryAgent:
    """
    Agent tự động khám phá và cào công thức nấu ăn từ các website Việt Nam.
    """

    JINA_SEARCH_PREFIX = "https://s.jina.ai/"

    def __init__(
        self,
        sites: Optional[list[str]] = None,
        delay_seconds: float = 2.0,
        max_recipes_per_run: int = 20,
    ):
        """
        Args:
            sites: Danh sách site keys (ví dụ: ["cooky", "savoury"]). 
                   None = tất cả.
            delay_seconds: Thời gian chờ giữa các request.
            max_recipes_per_run: Số công thức tối đa mỗi lần chạy.
        """
        self.sites = sites or list(SITE_CONFIGS.keys())
        self.delay = delay_seconds
        self.max_recipes = max_recipes_per_run

        settings = get_settings()
        self.jina_api_key = getattr(settings, "jina_api_key", "")

    # ------------------------------------------------------------------
    # Step 1: Discover links
    # ------------------------------------------------------------------
    async def discover_links(self, site_key: str) -> list[str]:
        """
        Tìm kiếm link công thức mới từ một website mục tiêu qua Jina Search.

        Args:
            site_key: Key của site (cooky, savoury, cookpad)

        Returns:
            Danh sách URL công thức
        """
        from urllib.parse import quote
        import json

        config = SITE_CONFIGS.get(site_key)
        if not config:
            logger.warning(f"Site '{site_key}' không được hỗ trợ.")
            return []

        all_urls: set[str] = set()

        for query in config["search_queries"]:
            # Retry logic for transient failures (timeout, network)
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    # URL-encode Vietnamese query text
                    encoded_query = quote(query, safe="")
                    search_url = f"{self.JINA_SEARCH_PREFIX}{encoded_query}"

                    headers: dict[str, str] = {
                        "User-Agent": "MenuGreenBot/1.0",
                        "Accept": "application/json",
                    }
                    if self.jina_api_key:
                        headers["Authorization"] = f"Bearer {self.jina_api_key}"

                    print(f"   🔎 Query: {query} (attempt {attempt + 1})")

                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            search_url, headers=headers, timeout=60
                        )

                    if response.status_code == 401:
                        print("\n❌ LỖI: Jina Search yêu cầu API Key.")
                        print("👉 Đăng ký miễn phí tại: https://jina.ai/reader/")
                        print("👉 Thêm vào .env: JINA_API_KEY=jina_...")
                        return []
                    elif response.status_code != 200:
                        print(f"   ⚠️ Jina trả về {response.status_code}, bỏ qua query này.")
                        break  # Don't retry on non-timeout HTTP errors

                    # Parse response (JSON or Markdown)
                    content = response.text
                    url_pattern = config["url_pattern"]

                    # Try JSON parsing first
                    try:
                        data = json.loads(content)
                        # Jina JSON response has "data" array with "url" fields
                        if isinstance(data, dict) and "data" in data:
                            for item in data["data"]:
                                url = item.get("url", "")
                                if re.search(url_pattern, url):
                                    all_urls.add(url)
                        print(f"   ✅ JSON parsed, found URLs so far: {len(all_urls)}")
                    except (json.JSONDecodeError, TypeError):
                        # Fallback: extract URLs from Markdown/text response
                        found_urls = re.findall(
                            r"https?://[^\s\)\]\"']+", content
                        )
                        for url in found_urls:
                            if re.search(url_pattern, url):
                                clean_url = re.sub(r"[),.\]]+$", "", url)
                                all_urls.add(clean_url)
                        print(f"   ✅ Text parsed, found URLs so far: {len(all_urls)}")

                    await asyncio.sleep(self.delay)
                    break  # Success, no need to retry

                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                    wait_time = (attempt + 1) * 5
                    print(f"   ⏱️ Timeout ({type(e).__name__}). ", end="")
                    if attempt < max_retries:
                        print(f"Thử lại sau {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print("Đã hết số lần thử. Bỏ qua query này.")

                except Exception as e:
                    error_msg = str(e) or repr(e)
                    print(f"   ❌ Lỗi: {type(e).__name__}: {error_msg}")
                    break  # Don't retry on unknown errors

        urls = list(all_urls)
        print(f"   🔗 [{config['name']}] Tổng: {len(urls)} link công thức")
        return urls

    # ------------------------------------------------------------------
    # Step 2: Crawl content
    # ------------------------------------------------------------------
    async def crawl_recipe(self, url: str) -> Optional[str]:
        """
        Đọc nội dung trang web công thức qua Jina Reader.

        Args:
            url: URL trang công thức

        Returns:
            Nội dung Markdown hoặc None nếu thất bại
        """
        try:
            content = await WebBrowserTool.read_url(url)

            if content.startswith("❌") or content.startswith("⚠️"):
                logger.warning(f"Không đọc được {url}: {content[:100]}")
                return None

            # Truncate nếu quá dài (giới hạn context cho LLM)
            max_chars = 8000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[... Nội dung bị cắt bớt ...]"

            return content

        except Exception as e:
            logger.error(f"Lỗi crawl {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Step 3: Extract structured recipe via LLM
    # ------------------------------------------------------------------
    async def extract_recipe(self, content: str, source_url: str) -> Optional[CleanedRecipe | str]:
        """
        Sử dụng Gemini để trích xuất thông tin công thức từ Markdown.

        Args:
            content: Nội dung Markdown của trang web
            source_url: URL gốc (để log)

        Returns:
            CleanedRecipe hoặc None nếu thất bại
        """
        import json
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0.2,
        )

        prompt = EXTRACTION_PROMPT.format(content=content)

        try:
            response = await llm.ainvoke([
                SystemMessage(content="You output valid JSON only."),
                HumanMessage(content=prompt),
            ])

            if not isinstance(response.content, str):
                logger.error(f"LLM trả về non-string cho {source_url}")
                return None

            # Clean markdown code blocks
            text = response.content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)

            # Check if it's a valid recipe (not an error response)
            if "error" in data:
                print(f"   ⏭️ Không phải trang công thức, bỏ qua.")
                return "SKIP"  # Sentinel value to indicate skip (not an error)

            # Build vector_text if missing
            vector_text = data.get("vector_text") or (
                f"{data['name']} {data.get('description', '')} "
                f"{' '.join(data.get('tags', []))}"
            )

            return CleanedRecipe(
                name=data["name"],
                description=data.get("description", ""),
                ingredients=data.get("ingredients", []),
                instructions=data.get("instructions", ""),
                prep_time_minutes=data.get("prep_time_minutes"),
                cook_time_minutes=data.get("cook_time_minutes"),
                servings=data.get("servings"),
                tags=data.get("tags", []),
                nutrients=data.get("nutrients"),
                vector_text=vector_text,
            )

        except Exception as e:
            logger.error(f"Lỗi extract recipe từ {source_url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Step 4: Dedup check
    # ------------------------------------------------------------------
    async def is_duplicate(self, recipe_name: str) -> bool:
        """
        Kiểm tra xem công thức đã tồn tại trong Database chưa.

        Args:
            recipe_name: Tên công thức

        Returns:
            True nếu đã tồn tại
        """
        try:
            client = SupabaseClient.get_client()
            result = (
                client.table("recipes")
                .select("id")
                .ilike("name", f"%{recipe_name}%")
                .limit(1)
                .execute()
            )
            return bool(result.data and len(result.data) > 0)
        except Exception as e:
            logger.error(f"Lỗi kiểm tra trùng lặp '{recipe_name}': {e}")
            return False  # Cho phép insert nếu không thể kiểm tra

    # ------------------------------------------------------------------
    # Step 5: Full pipeline
    # ------------------------------------------------------------------
    async def run(
        self,
        max_recipes: Optional[int] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Chạy toàn bộ pipeline Auto-Discovery.

        Args:
            max_recipes: Override số công thức tối đa
            dry_run: Nếu True, chỉ tìm + trích xuất, KHÔNG insert vào DB

        Returns:
            Dict thống kê kết quả
        """
        max_count = max_recipes or self.max_recipes
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n{'='*60}")
        print(f"🤖 AUTO-DISCOVERY AGENT — {timestamp}")
        print(f"{'='*60}")
        print(f"📌 Sites: {', '.join(self.sites)}")
        print(f"📌 Max recipes: {max_count}")
        print(f"📌 Dry run: {'YES' if dry_run else 'NO'}")
        print(f"{'='*60}\n")

        stats = {
            "links_found": 0,
            "crawled": 0,
            "extracted": 0,
            "duplicates": 0,
            "stored": 0,
            "skipped": 0,
            "errors": 0,
        }
        stored_recipes: list[CleanedRecipe] = []

        # Step 1: Discover links from all sites
        all_urls: list[str] = []
        for site_key in self.sites:
            config = SITE_CONFIGS.get(site_key)
            if not config:
                print(f"⚠️ Site '{site_key}' không được hỗ trợ, bỏ qua.")
                continue

            print(f"\n🔍 Đang tìm kiếm trên {config['name']}...")
            urls = await self.discover_links(site_key)
            all_urls.extend(urls)

        stats["links_found"] = len(all_urls)
        print(f"\n📊 Tổng link tìm được: {len(all_urls)}")

        if not all_urls:
            print("❌ Không tìm thấy link nào. Kết thúc.")
            return stats

        # Pre-filter: remove obvious non-recipe URLs (tag, category, pagination)
        filtered_urls = []
        for url in all_urls:
            is_listing = any(re.search(pat, url) for pat in SKIP_URL_PATTERNS)
            if is_listing:
                stats["skipped"] += 1
            else:
                filtered_urls.append(url)

        if stats["skipped"] > 0:
            print(f"🔽 Đã lọc bỏ {stats['skipped']} trang danh mục/tag")
            print(f"📋 Còn {len(filtered_urls)} link công thức tiềm năng")

        # Step 2-4: Crawl, extract, dedup for each URL
        for i, url in enumerate(filtered_urls):
            if stats["stored"] >= max_count:
                print(f"\n✅ Đã đạt giới hạn {max_count} công thức. Dừng.")
                break

            print(f"\n--- [{i+1}/{len(filtered_urls)}] {url[:70]}...")

            # Crawl
            content = await self.crawl_recipe(url)
            if not content:
                stats["errors"] += 1
                continue
            stats["crawled"] += 1
            print(f"   📄 Đã crawl ({len(content)} ký tự)")

            # Extract
            result = await self.extract_recipe(content, url)
            if result == "SKIP":
                stats["skipped"] += 1
                continue
            if not result:
                stats["errors"] += 1
                continue
            assert isinstance(result, CleanedRecipe)
            recipe = result
            stats["extracted"] += 1
            print(f"   🧹 Đã trích xuất: {recipe.name}")

            # Dedup
            if await self.is_duplicate(recipe.name):
                stats["duplicates"] += 1
                print(f"   ⏭️ Trùng lặp, bỏ qua.")
                continue

            # Store (or dry-run)
            if dry_run:
                print(f"   🔍 [DRY-RUN] Sẽ insert: {recipe.name}")
                print(f"      Tags: {recipe.tags}")
                print(f"      Nutrients: {recipe.nutrients}")
                stats["stored"] += 1
            else:
                try:
                    await process_and_store([recipe])
                    stats["stored"] += 1
                    stored_recipes.append(recipe)
                    print(f"   ✅ Đã lưu: {recipe.name}")
                except Exception as e:
                    stats["errors"] += 1
                    print(f"   ❌ Lỗi lưu: {e}")

            # Rate limiting
            await asyncio.sleep(self.delay)

        # Summary
        print(f"\n{'='*60}")
        print(f"📊 KẾT QUẢ AUTO-DISCOVERY")
        print(f"{'='*60}")
        print(f"   🔗 Link tìm thấy:     {stats['links_found']}")
        print(f"   🔽 Lọc bỏ (non-recipe):{stats['skipped']}")
        print(f"   📄 Crawl thành công:   {stats['crawled']}")
        print(f"   🧹 Trích xuất OK:      {stats['extracted']}")
        print(f"   ⏭️  Trùng lặp:          {stats['duplicates']}")
        print(f"   ✅ Đã lưu mới:         {stats['stored']}")
        print(f"   ❌ Lỗi:                {stats['errors']}")
        print(f"{'='*60}\n")

        return stats
