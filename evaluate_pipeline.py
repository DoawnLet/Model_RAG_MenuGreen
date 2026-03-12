"""
Evaluation Script for Menu Green Pipeline.
Tests the "Office Worker / Raining" scenario.
"""
from app.core.matching import check_ingredients_match

# Mock Data for Testing
MOCK_RECIPES = [
    {
        "name": "Mì cay Hàn Quốc",
        "tags": ["#spicy", "#warming", "#high-carb"],
        "ingredients": ["mì", "xúc xích", "ớt", "cải thảo"]
    },
    {
        "name": "Salad ức gà",
        "tags": ["#cooling", "#high-protein", "#no-sleepy", "#quick-lunch"],
        "ingredients": ["ức gà", "xà lách", "cà chua"]
    },
    {
        "name": "Súp bí đỏ kem tươi",
        "tags": ["#warming", "#no-sleepy", "#office-friendly"],
        "ingredients": ["bí đỏ", "kem tươi", "hành tây"]
    }
]

def evaluate_scenario(role: str, weather: str, time_limit: int):
    """
    Simulate logic for "I am {role}, it's {weather} and I have {time_limit} mins".
    
    Logic to test:
    - Office Worker -> prefer #no-sleepy, #office-friendly
    - Raining -> prefer #warming
    - Time < 15 -> prefer #quick-lunch
    """
    print(f"\n🧪 Testing Scenario: Role={role}, Weather={weather}, Time={time_limit}m")
    
    # 1. Define Filter Criteria based on inputs
    required_tags = []
    excluded_tags = []
    
    if role == "office":
        required_tags.append("#office-friendly")
        # Maybe #no-sleepy is good too
    
    if weather == "raining":
        required_tags.append("#warming")
        excluded_tags.append("#cooling") # Avoid cold food
        
    if time_limit < 15:
        required_tags.append("#quick-lunch")
        
    print(f"   📋 Requirements: Must have ONE of {required_tags}, Exclude {excluded_tags}")
    
    # 2. Filter Recipes
    valid_recipes = []
    for r in MOCK_RECIPES:
        score = 0
        tags = r["tags"]
        
        # Check Exclusions
        if any(t in tags for t in excluded_tags):
            continue
            
        # Check Requirements (Simple scoring)
        matched_tags = [t for t in tags if t in required_tags]
        score = len(matched_tags)
        
        # Special logic: Office Worker should avoid Mì cay (sweaty/spicy)?
        # Let's say if "office" and "spicy" -> penalty
        if role == "office" and "#spicy" in tags:
            score -= 10
            
        if score > 0:
            valid_recipes.append((r["name"], score))
            
    # Sort by score
    valid_recipes.sort(key=lambda x: x[1], reverse=True)
    
    print("   👉 Recommendations:")
    if valid_recipes:
        for name, score in valid_recipes:
            print(f"      - {name} (Score: {score})")
    else:
        print("      (No suitable recipes found)")

def test_set_matching():
    print("\n🧪 Testing Set Theory Matching (Saving Tier)")
    inventory = ["ức gà", "cà chua", "xà lách", "sốt mayonnaise"]
    requirements = ["ức gà", "xà lách"] # Recipe: Salad
    
    match, percent = check_ingredients_match(inventory, requirements)
    print(f"   Inventory: {inventory}")
    print(f"   Recipe Needs: {requirements}")
    print(f"   Match: {match} ({percent:.1%})")
    
    if match:
        print("   ✅ Valid for Saving Tier (No shopping needed)")
    else:
        print("   ❌ Need to buy ingredients")

if __name__ == "__main__":
    # Scenario: Office worker, Raining, 10 mins (Impossible combo? Let's see)
    # Salad is quick but cooling (bad for rain).
    # Súp bí đỏ is warming + office friendly but maybe not quick? (Let's assume we didn't tag it quick)
    evaluate_scenario(role="office", weather="raining", time_limit=10)
    
    test_set_matching()
