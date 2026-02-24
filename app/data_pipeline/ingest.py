"""
Unified Data Ingestion Script for Menu Green.
Combines scraping, cleaning, and storage into one workflow.

Usage:
    # Generate and ingest synthetic Vietnamese recipes
    python -m app.data_pipeline.ingest --mode synthetic --count 20
    
    # Scrape and ingest from URLs file
    python -m app.data_pipeline.ingest --mode scrape --urls urls.txt
    
    # Clean and ingest from raw JSON file
    python -m app.data_pipeline.ingest --mode file --input raw_recipes.json
"""
import asyncio
import argparse
import json
from pathlib import Path

from app.data_pipeline.scraper import RecipeScraper, generate_synthetic_recipes, RawRecipe
from app.data_pipeline.cleaner import RecipeCleaner, CleanedRecipe, process_and_store
from app.data_pipeline.csv_ingest import ingest_csv
from app.data_pipeline.auto_discovery import AutoDiscoveryAgent
from app.core.supabase_client import SupabaseClient



async def ingest_synthetic(count: int):
    """Generate synthetic recipes and ingest them in batches."""
    print(f"\n🚀 Starting SYNTHETIC ingestion: Target {count} recipes\n")
    
    # Batch size increased to reduce API calls
    BATCH_SIZE = 20 
    total_processed = 0
    
    # Diverse categories to ensure variety
    categories = [
        "Món Canh / Súp", "Món Kho (Thịt/Cá)", "Món Xào", "Món Chiên / Rán",
        "Món Nướng", "Món Hấp / Luộc", "Món Gỏi / Nộm", "Món Bún / Phở / Mì",
        "Món Cuốn", "Món Chay", "Món Tráng Miệng", "Đồ Uống Healthy",
        "Món Ăn Sáng", "Món Ăn Nhẹ / Snack", "Đặc Sản Miền Bắc",
        "Đặc Sản Miền Trung", "Đặc Sản Miền Tây"
    ]
    
    import random
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
    
    # Retry decorator for generation
    def log_retry(retry_state):
        if retry_state.next_action and hasattr(retry_state.next_action, 'sleep'):
            print(f"⚠️ Quota hit. Retrying in {retry_state.next_action.sleep}s...")
        else:
            print(f"⚠️ Quota hit. Retrying...")
    
    @retry(
        retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10),
        before_sleep=log_retry
    )
    async def generate_batch_safe(batch_size, category):
         return await generate_synthetic_recipes(batch_size, category=category)

    while total_processed < count:
        current_batch_size = min(BATCH_SIZE, count - total_processed)
        category = categories[total_processed % len(categories)]
        
        # Add some randomness to category selection if we loop many times
        if total_processed > len(categories) * BATCH_SIZE:
             category = random.choice(categories)
             
        try:
            # Step 1: Generate with retry
            recipes = await generate_batch_safe(current_batch_size, category)
            
            if not recipes:
                print("❌ No recipes generated in this batch. Retrying...")
                await asyncio.sleep(2)
                continue
            
            # Step 2: Convert to CleanedRecipe format
            cleaned = []
            for r in recipes:
                # Generate vector_text if not present
                vector_text = r.get("vector_text") or f"{r['name']} {r.get('description', '')} {' '.join(r.get('tags', []))}"
                
                cleaned.append(CleanedRecipe(
                    name=r["name"],
                    description=r.get("description", ""),
                    ingredients=r.get("ingredients", []),
                    instructions=r.get("instructions", ""),
                    prep_time_minutes=r.get("prep_time_minutes"),
                    cook_time_minutes=r.get("cook_time_minutes"),
                    servings=r.get("servings"),
                    tags=r.get("tags", []),
                    nutrients=r.get("nutrients", r.get("macros_estimate")),
                    vector_text=vector_text,
                ))
            
            # Step 3: Store
            # Note: storing also calls embeddings API, which might rate limit. 
            # We assume SupabaseClient.create_embedding handles simple retries or we rely on logic there.
            # Ideally we'd wrap this too, but let's start with generation which is the main bottleneck.
            await process_and_store(cleaned)
            total_processed += len(cleaned)
            print(f"📊 Progress: {total_processed}/{count} recipes ingested.\n")
            
            # Rate limiting / Backoff
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"⚠️ Error in batch: {e}")
            await asyncio.sleep(10)
            
    print(f"\n✅ Completed ingestion of {total_processed} recipes!")


async def ingest_from_urls(urls_file: str):
    """Scrape recipes from URLs and ingest them."""
    print(f"\n🚀 Starting SCRAPE ingestion from: {urls_file}\n")
    
    # Read URLs
    urls = Path(urls_file).read_text().strip().split("\n")
    urls = [u.strip() for u in urls if u.strip()]
    
    if not urls:
        print("❌ No URLs found!")
        return
    
    # Step 1: Scrape
    scraper = RecipeScraper(delay_seconds=1.5)
    raw_recipes = await scraper.scrape_multiple(urls)
    
    if not raw_recipes:
        print("❌ No recipes scraped!")
        return
    
    # Step 2: Clean with LLM
    cleaner = RecipeCleaner()
    cleaned = await cleaner.clean_batch(raw_recipes, concurrency=3)
    
    # Step 3: Store
    await process_and_store(cleaned)


async def ingest_from_file(json_file: str):
    """Ingest recipes from a raw JSON file."""
    print(f"\n🚀 Starting FILE ingestion from: {json_file}\n")
    
    # Read file
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    recipes = data if isinstance(data, list) else data.get("recipes", [])
    
    if not recipes:
        print("❌ No recipes found in file!")
        return
    
    # Convert to RawRecipe
    raw_recipes = []
    for r in recipes:
        # Handle both structured and unstructured formats
        if "raw_ingredients" in r:
            raw_recipes.append(RawRecipe(**r))
        else:
            # Already structured, convert to CleanedRecipe directly
            pass
    
    if raw_recipes:
        # Need cleaning
        cleaner = RecipeCleaner()
        cleaned = await cleaner.clean_batch(raw_recipes, concurrency=3)
        await process_and_store(cleaned)
    else:
        # Already clean, just convert and store
        cleaned = [
            CleanedRecipe(
                name=r["name"],
                description=r.get("description", ""),
                ingredients=r.get("ingredients", []),
                instructions=r.get("instructions", ""),
                prep_time_minutes=r.get("prep_time_minutes"),
                cook_time_minutes=r.get("cook_time_minutes"),
                servings=r.get("servings"),
                tags=r.get("tags", []),
                    nutrients=r.get("nutrients", r.get("macros_estimate")),
                vector_text=r.get("vector_text", r["name"]),
            )
            for r in recipes
        ]
        await process_and_store(cleaned)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Menu Green Data Ingestion")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "scrape", "file", "csv", "discover"],
        required=True,
        help="Ingestion mode",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of synthetic recipes to generate",
    )
    parser.add_argument(
        "--urls",
        type=str,
        help="Path to file containing URLs to scrape",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to input file (JSON for file mode, CSV for csv mode)",
    )
    
    args = parser.parse_args()
    
    if args.mode == "synthetic":
        asyncio.run(ingest_synthetic(args.count))
    elif args.mode == "scrape":
        if not args.urls:
            print("❌ --urls is required for scrape mode!")
            return
        asyncio.run(ingest_from_urls(args.urls))
    elif args.mode == "file":
        if not args.input:
            print("❌ --input is required for file mode!")
            return
        asyncio.run(ingest_from_file(args.input))
    elif args.mode == "csv":
        if not args.input:
            print("❌ --input is required for csv mode!")
            return
        asyncio.run(ingest_csv(args.input, limit=args.count))
    elif args.mode == "discover":
        agent = AutoDiscoveryAgent(max_recipes_per_run=args.count)
        asyncio.run(agent.run(max_recipes=args.count))



if __name__ == "__main__":
    main()
