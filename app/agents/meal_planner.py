"""
Meal Planning Agents - 5-step pipeline for 7-day meal planning.

Pipeline:
1. nutrition_analyzer → Calculate BMR/TDEE/Macros
2. recipe_retriever → RAG search for recipes
3. meal_planner → Optimize allocation
4. recipe_adapter → Adapt recipes to Vietnamese
5. validation_shopping → Validate & generate shopping list
"""
from typing import Optional
from datetime import date, timedelta
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import json
import asyncio
import logging

from app.agents.state import AgentState
from app.models.meal_plan import (
    NutritionTargets,
    MealDistribution,
    RecipeIngredient,
    RecipeNutrition,
    AdaptedRecipe,
    Meal,
    DailyMealPlan,
    ShoppingListItem,
    UserInfo,
    UserInfo,
    MealPlanOutput,
    SearchQueries,
    WeeklyMealPlanAllocation, 
    DailyAllocation,
)
from app.agents.nutrition import calculate_bmr, calculate_tdee, calculate_target_calories, UserProfile
from app.agents.rag_tool import RAGTool
from app.core.supabase_client import SupabaseClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================================
# STEP 1: NUTRITION ANALYZER AGENT
# ============================================================================

NUTRITION_ANALYZER_PROMPT = """
Bạn là chuyên gia dinh dưỡng của Menu Green. Nhiệm vụ: Xác định phân bổ bữa ăn tối ưu.

**Thông tin nhận được:**
- Mục tiêu: {goal}
- Mức độ hoạt động: {activity_level}
- BMR: {bmr} kcal/ngày
- TDEE: {tdee} kcal/ngày
- Target calories: {target_calories} kcal/ngày
- Protein target: {protein_g}g
- Carbs target: {carbs_g}g
- Fat target: {fat_g}g

**Nhiệm vụ của bạn:**
1. Xác định phân bổ % calories cho 4 bữa (sáng/trưa/tối/phụ)
2. Điều chỉnh dựa trên:
   - Văn phòng: Bữa trưa quan trọng (35-40%), sáng nhẹ (20-25%)
   - Tập gym: Phân bổ đều hơn, snack trước/sau tập (15%)
   - Giảm cân: Tối nhẹ hơn (25%), sáng đầy đủ (30%)

**Output (JSON only, không giải thích):**
{{
  "breakfast_percent": 0.25,
  "lunch_percent": 0.35,
  "dinner_percent": 0.30,
  "snack_percent": 0.10
}}
"""


async def nutrition_analyzer_agent(state: AgentState) -> dict:
    """
    STEP 1: Phân tích profile và tính BMR/TDEE/Macros + meal distribution.

    Args:
        state: AgentState với user_profile

    Returns:
        Updated state với nutrition_targets populated
    """
    try:
        profile_data = state.get("user_profile")

        if not profile_data:
            return {
                "validation_errors": ["Chưa có hồ sơ sức khỏe. Vui lòng cập nhật profile trước khi tạo meal plan."],
                "messages": [AIMessage(content="❌ Thiếu hồ sơ người dùng. Vui lòng cập nhật thông tin cá nhân.")]
            }

        # Calculate nutrition metrics
        profile = UserProfile(**profile_data)
        bmr = calculate_bmr(profile)
        tdee = calculate_tdee(profile)
        target_cals = calculate_target_calories(profile)

        # Calculate macros based on goal
        if profile.goal == "lose_fat":
            protein_percent, carb_percent, fat_percent = 0.35, 0.30, 0.35
        elif profile.goal == "gain_muscle":
            protein_percent, carb_percent, fat_percent = 0.30, 0.45, 0.25
        else:  # maintain
            protein_percent, carb_percent, fat_percent = 0.30, 0.40, 0.30

        protein_g = (target_cals * protein_percent) / 4
        carbs_g = (target_cals * carb_percent) / 4
        fat_g = (target_cals * fat_percent) / 9

        # Call LLM to determine optimal meal distribution
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

        prompt = NUTRITION_ANALYZER_PROMPT.format(
            goal=profile.goal,
            activity_level=profile.activity_level,
            bmr=bmr,
            tdee=tdee,
            target_calories=target_cals,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
        )

        # Structured Output
        structured_llm = llm.with_structured_output(MealDistribution)
        distribution_data: MealDistribution = await structured_llm.ainvoke(prompt)
        
        # Convert to dict for storage if needed, or keep as model.
        # But downstream expects dict access like ['breakfast_percent'].
        # Let's convert to dict to be safe with existing code structure or update downstream.
        # The nutrition_targets dict below expects 'meal_distribution' to be the data.

        nutrition_targets = {
            "daily_calories": target_cals,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "meal_distribution": distribution_data.model_dump()
        }

        logger.info(f"✅ Nutrition analysis complete: {target_cals} kcal/day")

        return {
            "nutrition_targets": nutrition_targets,
            "messages": [AIMessage(
                content=f"✅Step 1/5: Đã phân tích dinh dưỡng\n"
                        f"- Calo/ngày: {target_cals:.0f} kcal\n"
                        f"- Protein: {protein_g:.0f}g | Carbs: {carbs_g:.0f}g | Fat: {fat_g:.0f}g\n"
                        f"- Phân bổ: Sáng {distribution_data['breakfast_percent']*100:.0f}%, "
                        f"Trưa {distribution_data['lunch_percent']*100:.0f}%, "
                        f"Tối {distribution_data['dinner_percent']*100:.0f}%, "
                        f"Phụ {distribution_data['snack_percent']*100:.0f}%"
            )]
        }

    except Exception as e:
        logger.error(f"Nutrition analyzer failed: {str(e)}")
        return {
            "validation_errors": [f"Lỗi tính toán dinh dưỡng: {str(e)}"],
            "messages": [AIMessage(content=f"❌ Lỗi Step 1: {str(e)}")]
        }


# ============================================================================
# STEP 2: RECIPE RETRIEVER AGENT
# ============================================================================

RECIPE_RETRIEVER_PROMPT = """
Tạo 4 truy vấn tìm kiếm recipes cho meal plan 7 ngày:

**Context:**
- Mục tiêu: {goal}
- Dietary preferences: {dietary_prefs}
- Allergies: {allergies}
- Activity level: {activity_level}

**Yêu cầu:**
1. Query 1: Món sáng nhanh, nhẹ (<20 phút)
2. Query 2: Món trưa đầy đủ, giàu protein (phù hợp {goal})
3. Query 3: Món tối cân bằng, dễ tiêu
4. Query 4: Snacks lành mạnh, tiện mang theo

Mỗi query nên bao gồm dietary preferences và tránh allergies.

**Output (JSON array):**
["query 1", "query 2", "query 3", "query 4"]
"""


async def recipe_retriever_agent(state: AgentState) -> dict:
    """
    STEP 2: Tìm kiếm 20-30 recipes từ database sử dụng RAG.

    Args:
        state: AgentState với nutrition_targets và user_profile

    Returns:
        Updated state với candidate_recipes populated
    """
    try:
        profile = state.get("user_profile", {})
        targets = state.get("nutrition_targets")
        inventory = state.get("context", {}).get("inventory", [])

        if not targets:
            return {
                "validation_errors": ["Missing nutrition targets from Step 1"],
                "messages": [AIMessage(content="❌ Thiếu thông tin dinh dưỡng từ Step 1")]
            }
        
        if not profile:
            profile = {}

        goal = profile.get("goal", "maintain")
        dietary = profile.get("dietary_preferences", [])
        allergies = profile.get("allergies", [])
        activity = profile.get("activity_level", "moderate")

        # Generate search queries using LLM
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0.3,
        )

        prompt = RECIPE_RETRIEVER_PROMPT.format(
            goal=goal,
            dietary_prefs=", ".join(dietary) if dietary else "Không hạn chế",
            allergies=", ".join(allergies) if allergies else "Không có",
            activity_level=activity
        )

        # Structured Output
        structured_llm = llm.with_structured_output(SearchQueries)
        result: SearchQueries = await structured_llm.ainvoke(prompt)
        queries = result.queries

        # RAG Search for each query
        client = SupabaseClient.get_client()
        rag = RAGTool(client, SupabaseClient.create_embedding)

        all_recipes = []
        for query in queries:
            recipes = await rag.search_by_text(query, limit=10)
            all_recipes.extend(recipes)

        # Remove duplicates (by id)
        seen_ids = set()
        unique_recipes = []
        for r in all_recipes:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_recipes.append(r)

        # Filter by allergies (simple string matching in description)
        if allergies:
            filtered = []
            for r in unique_recipes:
                desc = (r.description or "").lower()
                if not any(allergy.lower() in desc for allergy in allergies):
                    filtered.append(r)
            unique_recipes = filtered

        # Fetch full recipe details from Supabase
        if not unique_recipes:
            return {
                "validation_errors": ["Không tìm thấy recipes phù hợp"],
                "messages": [AIMessage(content="❌ Không tìm thấy món ăn nào phù hợp. Vui lòng thử lại hoặc điều chỉnh dietary preferences.")]
            }

        recipe_ids = [r.id for r in unique_recipes[:30]]  # Limit to 30
        full_recipes = client.table("recipes") \
            .select("*, recipe_ingredients(*, ingredients(*))") \
            .in_("id", recipe_ids) \
            .execute()

        logger.info(f"✅ Found {len(full_recipes.data)} candidate recipes")

        return {
            "candidate_recipes": full_recipes.data,
            "messages": [AIMessage(
                content=f"✅ Step 2/5: Đã tìm thấy {len(full_recipes.data)} công thức phù hợp từ database"
            )]
        }

    except Exception as e:
        logger.error(f"Recipe retriever failed: {str(e)}")
        return {
            "validation_errors": [f"Lỗi tìm kiếm recipes: {str(e)}"],
            "messages": [AIMessage(content=f"❌ Lỗi Step 2: {str(e)}")]
        }


# ============================================================================
# STEP 3: MEAL PLANNER AGENT
# ============================================================================

MEAL_PLANNER_PROMPT = """
Bạn là Meal Planner AI. Phân bổ recipes cho 7 ngày thực đơn.

**Targets mỗi ngày:**
- Total: {daily_calories} kcal
- Sáng: {breakfast_calo} kcal
- Trưa: {lunch_calo} kcal
- Tối: {dinner_calo} kcal
- Phụ: {snack_calo} kcal
- Protein: ≥{protein_g}g (phân bổ ≥3 bữa)

**Constraints:**
1. Mỗi ngày ±100 kcal target
2. Không lặp món >2 lần/tuần
3. ≥3 bữa có protein cao (>15g) mỗi ngày
4. Sáng: Nhanh <20p, Trưa: Đầy đủ, Tối: Nhẹ, Phụ: Tiện

**Available recipes ({num_recipes} món):**
{recipe_list}

**Output JSON:**
{{
  "allocations": [
    {{"breakfast": "uuid", "lunch": "uuid", "dinner": "uuid", "snack": "uuid"}}, // Day 1
    ...
    {{"breakfast": "uuid", "lunch": "uuid", "dinner": "uuid", "snack": "uuid"}}  // Day 7
  ]
}}
"""


async def meal_planner_agent(state: AgentState) -> dict:
    """
    STEP 3: Phân bổ recipes vào 7 ngày sử dụng constraint satisfaction.

    Args:
        state: AgentState với nutrition_targets và candidate_recipes

    Returns:
        Updated state với meal_plan_draft populated
    """
    try:
        targets = state.get("nutrition_targets")
        recipes = state.get("candidate_recipes", [])

        if not recipes:
            return {
                "validation_errors": ["No candidate recipes from Step 2"],
                "messages": [AIMessage(content="❌ Không có recipes từ Step 2")]
            }
        
        if not targets:
            return {
                "validation_errors": ["Missing nutrition targets"],
                "messages": [AIMessage(content="❌ Thiếu thông tin dinh dưỡng")]
            }

        # Prepare recipe summary for LLM
        recipe_summary = []
        for r in recipes[:25]:  # Limit context size
            # Calculate total calories from ingredients
            total_cals = 0
            total_protein = 0
            for ing in r.get("recipe_ingredients", []):
                ing_data = ing.get("ingredients", {})
                amount = ing.get("amount", 0)
                cals_per_100g = ing_data.get("calories_per_100g", 0)
                protein_per_100g = ing_data.get("protein_per_100g", 0)
                total_cals += (amount / 100) * cals_per_100g
                total_protein += (amount / 100) * protein_per_100g

            prep_time = (r.get("prep_time_minutes", 0) or 0) + (r.get("cook_time_minutes", 0) or 0)

            recipe_summary.append({
                "id": r["id"],
                "name": r["name"],
                "calories": round(total_cals),
                "protein": round(total_protein),
                "prep_time": prep_time
            })

        # Call LLM for optimization
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0.3,
        )

        dist = targets["meal_distribution"]
        prompt = MEAL_PLANNER_PROMPT.format(
            daily_calories=targets["daily_calories"],
            breakfast_calo=targets["daily_calories"] * dist["breakfast_percent"],
            lunch_calo=targets["daily_calories"] * dist["lunch_percent"],
            dinner_calo=targets["daily_calories"] * dist["dinner_percent"],
            snack_calo=targets["daily_calories"] * dist["snack_percent"],
            protein_g=targets["protein_g"],
            num_recipes=len(recipe_summary),
            recipe_list=json.dumps(recipe_summary, ensure_ascii=False, indent=2)
        )

        # Structured Output
        structured_llm = llm.with_structured_output(WeeklyMealPlanAllocation)
        result: WeeklyMealPlanAllocation = await structured_llm.ainvoke(prompt)
        
        # Convert to dictionary format expected by downstream agent (day_1, day_2 keys)
        
        allocation = {}
        for idx, day_alloc in enumerate(result.allocations, 1):
             allocation[f"day_{idx}"] = day_alloc.model_dump()

        logger.info("✅ Meal allocation complete for 7 days")

        return {
            "meal_plan_draft": allocation,
            "messages": [AIMessage(
                content="✅ Step 3/5: Đã phân bổ thực đơn 7 ngày (28 bữa)"
            )]
        }

    except Exception as e:
        logger.error(f"Meal planner failed: {str(e)}")
        return {
            "validation_errors": [f"Lỗi optimization: {str(e)}"],
            "messages": [AIMessage(content=f"❌ Lỗi Step 3: {str(e)}")]
        }


# ============================================================================
# STEP 4: RECIPE ADAPTER AGENT
# ============================================================================

RECIPE_ADAPTER_PROMPT = """
Adapt công thức món ăn sang tiếng Việt chi tiết.

**Recipe gốc:**
- Tên: {name}
- Thời gian: {prep_time} phút
- Nguyên liệu: {ingredients}
- Cách làm: {instructions}

**Requirements:**
- Target calories: {target_calo} kcal (bữa {meal_type})
- Allergies cần tránh: {allergies}
- Nguyên liệu có sẵn: {inventory_items}

**Nhiệm vụ:**
1. Scale portions để match target calories (±50 kcal)
2. Thay thế allergies nếu có (VD: đậu nành → thịt gà)
3. Đánh dấu nguyên liệu có trong kho (in_inventory: true)
4. Viết cách làm tiếng Việt, từng bước, dễ hiểu

**Output (JSON only):**
{{
  "ten": "Tên món tiếng Việt",
  "thoi_gian_nau": 20,
  "nguyen_lieu": [
    {{"name": "Thịt gà", "amount": 150, "unit": "g", "calories": 165, "protein": 31, "in_inventory": true}}
  ],
  "cach_lam": ["Bước 1: ...", "Bước 2: ..."],
  "dinh_duong": {{"calories": {target_calo}, "protein_g": 30, "carbs_g": 20, "fat_g": 10}},
  "ghi_chu": "Tips nếu có"
}}
"""


async def recipe_adapter_agent(state: AgentState) -> dict:
    """
    STEP 4: Adapt mỗi recipe trong draft plan thành AdaptedRecipe tiếng Việt.

    Args:
        state: AgentState với meal_plan_draft và candidate_recipes

    Returns:
        Updated state với final_meal_plan populated
    """
    try:
        draft = state.get("meal_plan_draft")
        recipes = state.get("candidate_recipes", [])
        targets = state.get("nutrition_targets")
        profile = state.get("user_profile", {})
        inventory = state.get("context", {}).get("inventory", [])

        if not draft:
            return {
                "validation_errors": ["Missing meal plan draft from Step 3"],
                "messages": [AIMessage(content="❌ Không có draft plan từ Step 3")]
            }
        
        if not targets:
            return {
                "validation_errors": ["Missing nutrition targets"],
                "messages": [AIMessage(content="❌ Thiếu thông tin dinh dưỡng")]
            }
        
        if not profile:
            profile = {}

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )

        # Build inventory names set for quick lookup
        inventory_names = set()
        for item in inventory:
            ing = item.get("ingredients", {})
            if "name" in ing:
                inventory_names.add(ing["name"].lower())

        allergies = profile.get("allergies", [])
        dist = targets["meal_distribution"]

        # Prepare all adaptation tasks
        adaptation_tasks = []
        task_metadata = []  # Store (day_num, meal_type) for each task

        for day_num in range(1, 8):
            day_key = f"day_{day_num}"
            day_allocation = draft.get(day_key, {})

            for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
                recipe_id = day_allocation.get(meal_type)
                if not recipe_id:
                    continue

                recipe_data = next((r for r in recipes if r["id"] == recipe_id), None)
                if not recipe_data:
                    logger.warning(f"Recipe ID {recipe_id} not found for day {day_num} {meal_type}")
                    continue

                # Calculate target for this meal
                meal_percent = dist[f"{meal_type}_percent"]
                target_calo = targets["daily_calories"] * meal_percent

                # Prepare ingredients string
                ingredients_list = []
                for ing in recipe_data.get("recipe_ingredients", []):
                    ing_data = ing.get("ingredients", {})
                    ingredients_list.append(
                        f"{ing_data.get('name', 'N/A')}: {ing.get('amount', 0)} {ing.get('unit', 'g')}"
                    )
                ingredients_str = "\n".join(ingredients_list)

                prompt = RECIPE_ADAPTER_PROMPT.format(
                    name=recipe_data["name"],
                    prep_time=(recipe_data.get("prep_time_minutes", 0) or 0) +
                             (recipe_data.get("cook_time_minutes", 0) or 0),
                    ingredients=ingredients_str,
                    instructions=recipe_data.get("instructions", "Không có hướng dẫn"),
                    target_calo=target_calo,
                    meal_type=meal_type,
                    allergies=", ".join(allergies) if allergies else "Không có",
                    inventory_items=", ".join(list(inventory_names)[:10]) if inventory_names else "Không có"
                )

                # Structured Output
                structured_llm = llm.with_structured_output(AdaptedRecipe)
                # Create async task
                adaptation_tasks.append(structured_llm.ainvoke(prompt))
                task_metadata.append((day_num, meal_type))

        # Execute all adaptations in parallel
        logger.info(f"Adapting {len(adaptation_tasks)} recipes in parallel...")
        responses = await asyncio.gather(*adaptation_tasks, return_exceptions=True)

        # Build days structure
        adapted_days = {}
        for (day_num, meal_type), response in zip(task_metadata, responses):
            # Skip exceptions - type guard
            if isinstance(response, Exception):
                logger.error(f"Adaptation failed for day {day_num} {meal_type}: {response}")
                continue
            
            # Response is now AdaptedRecipe object (or should be)
            if not isinstance(response, AdaptedRecipe):
                 logger.error(f"Invalid response type for day {day_num} {meal_type}: {type(response)}")
                 continue

            try:
                adapted_json = response.model_dump()

                # Mark in_inventory
                for ing in adapted_json.get("nguyen_lieu", []):
                    if ing["name"].lower() in inventory_names:
                        ing["in_inventory"] = True

                # Group by day
                if day_num not in adapted_days:
                    adapted_days[day_num] = []

                meal_type_vn = {
                    "breakfast": "sáng",
                    "lunch": "trưa",
                    "dinner": "tối",
                    "snack": "phụ"
                }[meal_type]

                adapted_days[day_num].append({
                    "loai": meal_type_vn,
                    "mon_an": adapted_json
                })

            except Exception as e:
                logger.error(f"Failed to parse adaptation for day {day_num} {meal_type}: {e}")
                continue

        # Build final structure
        final_days = []
        for day_num in range(1, 8):
            if day_num not in adapted_days:
                logger.warning(f"Day {day_num} has no meals, skipping...")
                continue

            daily_meals = adapted_days[day_num]
            total_calo = sum(m["mon_an"]["dinh_duong"]["calories"] for m in daily_meals)

            final_days.append({
                "ngay": day_num,
                "ngay_thuc": (date.today() + timedelta(days=day_num - 1)).isoformat(),
                "tong_calo": total_calo,
                "buoi_an": daily_meals
            })

        logger.info(f"✅ Adapted {len(final_days)} days successfully")

        return {
            "final_meal_plan": {"thuc_don_7_ngay": final_days},
            "messages": [AIMessage(
                content=f"✅ Step 4/5: Đã adapt {len(final_days)} ngày thực đơn chi tiết"
            )]
        }

    except Exception as e:
        logger.error(f"Recipe adapter failed: {str(e)}")
        return {
            "validation_errors": [f"Lỗi adaptation: {str(e)}"],
            "messages": [AIMessage(content=f"❌ Lỗi Step 4: {str(e)}")]
        }


# ============================================================================
# STEP 5: VALIDATION & SHOPPING LIST AGENT
# ============================================================================

async def validation_shopping_agent(state: AgentState) -> dict:
    """
    STEP 5: Validate meal plan + generate shopping list + assemble final output.

    Args:
        state: AgentState với final_meal_plan

    Returns:
        Updated state với validated final_meal_plan và JSON output in messages
    """
    try:
        meal_plan = state.get("final_meal_plan")
        targets = state.get("nutrition_targets")
        profile = state.get("user_profile", {})
        inventory = state.get("context", {}).get("inventory", [])

        if not meal_plan:
            return {
                "validation_errors": ["Missing final meal plan from Step 4"],
                "messages": [AIMessage(content="❌ Không có meal plan từ Step 4")]
            }
        
        if not targets:
            return {
                "validation_errors": ["Missing nutrition targets"],
                "messages": [AIMessage(content="❌ Thiếu thông tin dinh dưỡng")]
            }
        
        if not profile:
            profile = {}

        days = meal_plan["thuc_don_7_ngay"]

        # Validation checks
        errors = []
        warnings = []

        for day in days:
            daily_calo = day["tong_calo"]
            target_calo = targets["daily_calories"]

            if abs(daily_calo - target_calo) > 150:
                warnings.append(
                    f"Ngày {day['ngay']}: Calo lệch {daily_calo - target_calo:.0f} kcal so với mục tiêu"
                )

            # Check protein distribution
            protein_meals = [
                m for m in day["buoi_an"]
                if m["mon_an"]["dinh_duong"]["protein_g"] > 15
            ]
            if len(protein_meals) < 3:
                warnings.append(
                    f"Ngày {day['ngay']}: Chỉ có {len(protein_meals)} bữa có protein cao (khuyến nghị ≥3)"
                )

        # Build shopping list
        inventory_names = set()
        for item in inventory:
            ing = item.get("ingredients", {})
            if "name" in ing:
                inventory_names.add(ing["name"].lower())

        shopping_dict = {}

        for day in days:
            for meal in day["buoi_an"]:
                for ing in meal["mon_an"]["nguyen_lieu"]:
                    name = ing["name"]
                    amount = ing["amount"]
                    unit = ing["unit"]

                    # Aggregate ingredients
                    if name not in shopping_dict:
                        shopping_dict[name] = {
                            "amount": 0,
                            "unit": unit,
                            "in_inventory": name.lower() in inventory_names
                        }
                    shopping_dict[name]["amount"] += amount

        shopping_list = [
            {
                "ten_nguyen_lieu": name,
                "so_luong": round(data["amount"], 1),
                "don_vi": data["unit"],
                "co_san_trong_kho": data["in_inventory"]
            }
            for name, data in shopping_dict.items()
        ]

        # Assemble final output
        goal_map = {
            "lose_fat": "Giảm mỡ",
            "maintain": "Duy trì",
            "gain_muscle": "Tăng cơ"
        }

        final_output = MealPlanOutput(
            thong_tin_nguoi_dung=UserInfo(
                ten=profile.get("name", "Người dùng"),
                muc_tieu=goal_map.get(profile.get("goal", "maintain"), "Duy trì"),
                calo_ngay=targets["daily_calories"],
                protein_g=targets["protein_g"]
            ),
            thuc_don_7_ngay=[DailyMealPlan(**day) for day in days],
            danh_sach_mua=[ShoppingListItem(**item) for item in shopping_list],
            ghi_chu=(
                f"Thực đơn được tạo bởi Menu Green AI cho {len(days)} ngày. "
                + (f"Có {len(warnings)} lưu ý cần xem xét." if warnings else "Thực đơn đã được tối ưu hoàn chỉnh!")
            )
        )

        # Return as formatted JSON string
        json_output = final_output.model_dump_json(indent=2, ensure_ascii=False)

        validation_msg = ""
        if warnings:
            validation_msg = "\n\n⚠️ Lưu ý:\n" + "\n".join(f"- {w}" for w in warnings)

        logger.info("✅ Meal plan validation and shopping list generation complete")

        return {
            "final_meal_plan": final_output.model_dump(),
            "validation_errors": errors if errors else None,
            "messages": [AIMessage(
                content=f"✅ Step 5/5: Hoàn tất meal plan!\n\n"
                        f"📊 Tổng quan:\n"
                        f"- {len(days)} ngày thực đơn\n"
                        f"- {len(shopping_list)} nguyên liệu cần mua\n"
                        f"- {len([i for i in shopping_list if i['co_san_trong_kho']])} nguyên liệu đã có sẵn"
                        f"{validation_msg}\n\n"
                        f"```json\n{json_output}\n```"
            )]
        }

    except Exception as e:
        logger.error(f"Validation/shopping agent failed: {str(e)}")
        return {
            "validation_errors": [f"Lỗi validation: {str(e)}"],
            "messages": [AIMessage(content=f"❌ Lỗi Step 5: {str(e)}")]
        }
