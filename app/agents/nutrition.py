"""
Nutrition Agent - Calculates BMR, TDEE, and Macro distributions.
Uses Mifflin-St Jeor equation for accuracy.
"""

from typing import Literal
from pydantic import BaseModel


class UserProfile(BaseModel):
    """User physiological profile for nutrition calculations."""

    weight_kg: float
    height_cm: float
    age: int
    gender: Literal["male", "female"]
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal: Literal["lose_fat", "maintain", "gain_muscle"]


class MacroDistribution(BaseModel):
    """Daily macro nutrient targets in grams."""

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


# Activity level multipliers for TDEE calculation
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,  # Little or no exercise
    "light": 1.375,  # Light exercise 1-3 days/week
    "moderate": 1.55,  # Moderate exercise 3-5 days/week
    "active": 1.725,  # Hard exercise 6-7 days/week
    "very_active": 1.9,  # Very hard exercise, physical job
}

# Goal adjustments for calorie targets
GOAL_ADJUSTMENTS = {
    "lose_fat": -500,  # Caloric deficit
    "maintain": 0,
    "gain_muscle": 300,  # Caloric surplus
}


def calculate_bmr(profile: UserProfile) -> float:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.

    Formula:
    - Male: BMR = 10*weight(kg) + 6.25*height(cm) - 5*age + 5
    - Female: BMR = 10*weight(kg) + 6.25*height(cm) - 5*age - 161

    Args:
        profile: User physiological profile

    Returns:
        BMR in calories/day
    """
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    s = 5 if profile.gender == "male" else -161
    return base + s


def calculate_tdee(profile: UserProfile) -> float:
    """
    Calculate Total Daily Energy Expenditure.

    TDEE = BMR * Activity Multiplier

    Args:
        profile: User physiological profile

    Returns:
        TDEE in calories/day
    """
    bmr = calculate_bmr(profile)
    multiplier = ACTIVITY_MULTIPLIERS[profile.activity_level]
    return bmr * multiplier


def calculate_target_calories(profile: UserProfile) -> float:
    """
    Calculate target daily calories based on goal.

    Args:
        profile: User physiological profile

    Returns:
        Target calories/day
    """
    tdee = calculate_tdee(profile)
    adjustment = GOAL_ADJUSTMENTS[profile.goal]
    return tdee + adjustment


def calculate_macros(
    profile: UserProfile,
    protein_ratio: float = 0.30,
    carb_ratio: float = 0.40,
    fat_ratio: float = 0.30,
) -> MacroDistribution:
    """
    Calculate macro distribution in grams based on calorie target.

    Default ratios: 30% Protein, 40% Carbs, 30% Fat (suitable for gym-goers)

    Calorie values per gram:
    - Protein: 4 kcal/g
    - Carbs: 4 kcal/g
    - Fat: 9 kcal/g

    Args:
        profile: User physiological profile
        protein_ratio: Percentage of calories from protein (0-1)
        carb_ratio: Percentage of calories from carbs (0-1)
        fat_ratio: Percentage of calories from fat (0-1)

    Returns:
        MacroDistribution with daily targets in grams
    """
    target_calories = calculate_target_calories(profile)

    protein_calories = target_calories * protein_ratio
    carb_calories = target_calories * carb_ratio
    fat_calories = target_calories * fat_ratio

    return MacroDistribution(
        calories=round(target_calories, 1),
        protein_g=round(protein_calories / 4, 1),  # 4 kcal per gram
        carbs_g=round(carb_calories / 4, 1),  # 4 kcal per gram
        fat_g=round(fat_calories / 9, 1),  # 9 kcal per gram
    )


def get_nutrition_summary(profile: UserProfile) -> str:
    """
    Generate a human-readable nutrition summary for the user.

    Args:
        profile: User physiological profile

    Returns:
        Formatted string with nutrition recommendations
    """
    bmr = calculate_bmr(profile)
    tdee = calculate_tdee(profile)
    macros = calculate_macros(profile)

    return f"""
📊 **Phân tích dinh dưỡng cá nhân**

🔥 **BMR (Năng lượng nghỉ ngơi):** {bmr:.0f} kcal/ngày
⚡ **TDEE (Năng lượng tiêu thụ):** {tdee:.0f} kcal/ngày
🎯 **Mục tiêu:** {macros.calories:.0f} kcal/ngày

📦 **Phân bổ Macro hàng ngày:**
- 🥩 Protein: {macros.protein_g:.0f}g
- 🍚 Carbs: {macros.carbs_g:.0f}g  
- 🥑 Fat: {macros.fat_g:.0f}g
"""
