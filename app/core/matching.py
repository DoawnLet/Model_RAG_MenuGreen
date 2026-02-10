"""
Matching Logic for Menu Green.
Implements Set Theory matching for "Saving Tier" (Zero Waste).
"""
import re

def normalize_ingredient(name: str) -> str:
    """
    Simple normalization for ingredients.
    "1kg ức gà" -> "ức gà"
    "Hành tây thái hạt lựu" -> "hành tây"
    """
    # Lowercase
    name = name.lower().strip()
    
    # Remove common units/quantities (very basic regex)
    # Remove leading numbers/units e.g. "100g ", "1 kg ", "2 quả "
    name = re.sub(r'^\d+(\s*(g|kg|ml|l|quả|trái|muỗng|thìa|bát|chén)\b)?\s*', '', name)
    
    # Remove processing descriptions e.g. "xắt nhỏ", "băm nhuyễn"
    # This is hard without NLP, but we do basic keyword removal
    remove_words = ["xắt", "thái", "băm", "nhuyễn", "lát", "hạt lựu", "tươi", "khô"]
    for word in remove_words:
        name = name.replace(word, "")
        
    return name.strip()


def check_ingredients_match(user_inventory: list[str], recipe_ingredients: list[str]) -> tuple[bool, float]:
    """
    Check if user has enough ingredients for the recipe using Set Theory.
    
    Logic:
    If (Recipe_Ingredients subset of User_Inventory) -> Perfect Match (100%)
    
    We calculate coverage: |Intersection| / |Recipe_Ingredients|
    
    Args:
        user_inventory: List of ingredient names user has
        recipe_ingredients: List of ingredient names in recipe
        
    Returns:
        (is_match, match_percentage)
    """
    if not recipe_ingredients:
        return True, 1.0 # No ingredients needed?
        
    user_set = set(normalize_ingredient(i) for i in user_inventory)
    recipe_set = set(normalize_ingredient(i) for i in recipe_ingredients)
    
    # Calculate intersection
    common = user_set.intersection(recipe_set)
    
    coverage = len(common) / len(recipe_set) if len(recipe_set) > 0 else 0.0
    
    # We consider it a "Saving Tier" match if strict coverage is high (e.g. > 80% or 100%)
    # User requirement: "If {chicken, mushroom} subset of {chicken, mushroom, onion} -> Valid"
    # This implies Recipe must be a subset of Inventory (or close).
    
    # Let's say 100% is ideal, but maybe allowing 1-2 missing spices is okay.
    # For now, let's return the Raw coverage.
    
    return coverage >= 0.8, coverage
