"""
CSV Ingestor for Global Datasets (Food.com / Recipe1M+).
Maps columns from Kaggle datasets to Menu Green schema.
"""
import asyncio
import pandas as pd
import ast
from typing import Optional, List
from app.data_pipeline.cleaner import CleanedRecipe, process_and_store

# Column mapping for Food.com dataset (update as needed)
# Typical columns: name, id, minutes, contributor_id, submitted, tags, nutrition, 
# n_steps, steps, description, ingredients, n_ingredients
COL_MAPPING = {
    "name": "name",
    "description": "description",
    "ingredients": "ingredients",  # String representation of list
    "steps": "instructions",       # String representation of list
    "minutes": "prep_time_minutes", # Rough estimate
    "tags": "tags",                # String representation of list
    "nutrition": "nutrition"       # [cal, fat, sugar, sodium, protein, sat_fat, carbs]
}

def parse_list_string(s: str) -> List[str]:
    """Parse string representation of list from CSV."""
    try:
        if not isinstance(s, str):
            return []
        return ast.literal_eval(s)
    except:
        return []

def parse_nutrition(s: str) -> dict:
    """
    Parse nutrition list string [cal, fat, sugar, sodium, protein, sat_fat, carbs].
    Returns macros_estimate dict.
    Note: Values in dataset are usually % Daily Value, except Calories.
    We need to be careful with units. For Food.com:
    - calories (#)
    - total fat (PDV)
    - sugar (PDV)
    - sodium (PDV)
    - protein (PDV)
    - saturated fat (PDV)
    - carbohydrates (PDV)
    
    This is an approximation.
    """
    try:
        vals = ast.literal_eval(s)
        if len(vals) >= 7:
            # Very rough conversion from PDV to grams if needed, 
            # or just store as is. For now, we'll just map what we can.
            # Let's assume standard 2000 kcal diet for PDV conversion ballpark?
            # Protein 50g = 100%, Carbs 275g = 100%, Fat 78g = 100%
            
            p_pdv = vals[4]
            c_pdv = vals[6]
            f_pdv = vals[1]
            
            return {
                "protein_g": round(p_pdv * 0.5, 1), # Rough estimate
                "carbs_g": round(c_pdv * 2.75, 1),
                "fat_g": round(f_pdv * 0.78, 1),
                "calories": vals[0]
            }
    except:
        pass
    return None

async def ingest_csv(csv_path: str, limit: int = 100):
    """
    Read CSV and ingest recipes.
    
    Args:
        csv_path: Path to CSV file
        limit: Max rows to process
    """
    print(f"📊 Reading CSV: {csv_path} (limit={limit})...")
    
    try:
        df = pd.read_csv(csv_path, nrows=limit)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    cleaned_recipes = []
    
    for _, row in df.iterrows():
        try:
            name = row.get(COL_MAPPING["name"], "Unknown")
            desc = str(row.get(COL_MAPPING["description"], ""))
            if desc == "nan": desc = ""
            
            ingredients = parse_list_string(row.get(COL_MAPPING["ingredients"], "[]"))
            instructions_list = parse_list_string(row.get(COL_MAPPING["steps"], "[]"))
            instructions = "\n".join(instructions_list)
            
            tags = parse_list_string(row.get(COL_MAPPING["tags"], "[]"))
            
            macros = parse_nutrition(row.get(COL_MAPPING["nutrition"], "[]"))
            
            minutes = row.get(COL_MAPPING["minutes"], 0)
            
            # Construct meaningful vector text for cross-lingual search
            # Include 'Recipe' keyword to help embedding model
            vector_text = f"Recipe: {name}. Description: {desc}. Keywords: {', '.join(tags)}"
            
            cleaned_recipes.append(CleanedRecipe(
                name=name,
                description=desc,
                ingredients=ingredients,
                instructions=instructions,
                prep_time_minutes=int(minutes),
                tags=tags,
                nutrients=macros,
                vector_text=vector_text
            ))
            
        except Exception as e:
            print(f"⚠️ Skipping row: {e}")
            continue
            
    if cleaned_recipes:
        print(f"✅ Parsed {len(cleaned_recipes)} recipes. Starting ingestion...")
        await process_and_store(cleaned_recipes)
    else:
        print("⚠️ No recipes parsed successfully.")
