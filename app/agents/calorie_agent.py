"""
app/agents/calorie_agent.py

Calorie Calculator Agent — Tính calo theo TÊN MÓN (không theo nguyên liệu).

Logic:
1. Tra cứu DB recipes → lấy calories_per_serving
2. Nếu không tìm thấy → hỏi Gemini ước tính
3. Trả về: "Phở bò 1 tô ≈ 450 kcal | Protein: 28g | Carbs: 55g | Fat: 12g"
"""

import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


# Bảng calo phổ biến (fallback nhanh, không cần DB/API)
COMMON_DISH_CALORIES = {
    "phở bò": {"calories": 450, "protein": 28, "carbs": 55, "fat": 12},
    "phở gà": {"calories": 380, "protein": 26, "carbs": 50, "fat": 8},
    "bún bò huế": {"calories": 430, "protein": 25, "carbs": 55, "fat": 14},
    "bún riêu": {"calories": 350, "protein": 22, "carbs": 48, "fat": 9},
    "bánh mì": {"calories": 400, "protein": 16, "carbs": 52, "fat": 14},
    "cơm tấm": {"calories": 650, "protein": 32, "carbs": 75, "fat": 22},
    "cơm rang": {"calories": 480, "protein": 15, "carbs": 68, "fat": 16},
    "mì xào": {"calories": 420, "protein": 18, "carbs": 60, "fat": 12},
    "gỏi cuốn": {"calories": 120, "protein": 8, "carbs": 18, "fat": 2},
    "chả giò": {"calories": 180, "protein": 7, "carbs": 16, "fat": 10},
    "canh chua": {"calories": 180, "protein": 18, "carbs": 12, "fat": 5},
    "thịt kho tàu": {"calories": 520, "protein": 28, "carbs": 18, "fat": 35},
    "cá kho tộ": {"calories": 320, "protein": 30, "carbs": 8, "fat": 18},
    "bún chả": {"calories": 480, "protein": 28, "carbs": 55, "fat": 16},
    "bún đậu mắm tôm": {"calories": 550, "protein": 22, "carbs": 62, "fat": 20},
    "bánh xèo": {"calories": 380, "protein": 14, "carbs": 42, "fat": 18},
    "salad": {"calories": 150, "protein": 6, "carbs": 20, "fat": 5},
    "smoothie": {"calories": 200, "protein": 4, "carbs": 42, "fat": 2},
    "trứng chiên": {"calories": 185, "protein": 13, "carbs": 1, "fat": 14},
    "cơm trắng": {"calories": 200, "protein": 4, "carbs": 44, "fat": 0},
}


def _lookup_local(dish_name: str) -> dict | None:
    """Tra cứu nhanh từ bảng local."""
    dish_lower = dish_name.strip().lower()
    # Tìm exact match trước
    if dish_lower in COMMON_DISH_CALORIES:
        return COMMON_DISH_CALORIES[dish_lower]
    # Tìm partial match
    for key, val in COMMON_DISH_CALORIES.items():
        if key in dish_lower or dish_lower in key:
            return val
    return None


def _lookup_db(dish_name: str) -> dict | None:
    """Tra cứu trong Supabase recipes table."""
    try:
        client = SupabaseClient.get_client()
        result = (
            client.table("recipes")
            .select(
                "name, calories_per_serving, protein_per_serving, carbs_per_serving, fat_per_serving"
            )
            .ilike("name", f"%{dish_name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            r = dict(result.data[0]) if isinstance(result.data[0], dict) else result.data[0] # type: ignore
            if r.get("calories_per_serving"): # type: ignore
                return {
                    "calories": r["calories_per_serving"],
                    "protein": r.get("protein_per_serving", 0),
                    "carbs": r.get("carbs_per_serving", 0),
                    "fat": r.get("fat_per_serving", 0),
                    "source": "database",
                    "recipe_name": r["name"],
                }
    except Exception as e:
        logger.warning(f"DB calorie lookup failed: {e}")
    return None


def _format_calorie_response(dish_name: str, data: dict, source: str = "local") -> str:
    """Format kết quả đẹp."""
    cal = data.get("calories", "?")
    pro = data.get("protein", "?")
    car = data.get("carbs", "?")
    fat = data.get("fat", "?")

    source_note = ""
    if source == "gemini":
        source_note = "\n_(Ước tính từ AI — có thể sai số ±15%)_"
    elif source == "database":
        source_note = f"\n_(Từ DB: {data.get('recipe_name', dish_name)})_"

    return f"""🍽️ **Thông tin dinh dưỡng: {dish_name.title()}** (1 khẩu phần)

| Thành phần | Lượng |
|-----------|-------|
| 🔥 Calories | **{cal} kcal** |
| 🥩 Protein | {pro}g |
| 🍚 Carbs | {car}g |
| 🥑 Fat | {fat}g |
{source_note}"""


async def calorie_lookup_agent(state: AgentState) -> dict:
    """
    Agent tính calo theo tên món ăn.

    Thứ tự ưu tiên:
    1. Bảng local (nhanh, 0ms)
    2. Database Supabase (chính xác nhất)
    3. Gemini AI ước tính (fallback)
    """
    last_message = state["messages"][-1]
    if not isinstance(last_message.content, str):
        return {"messages": [AIMessage(content="❌ Không hiểu yêu cầu.")]}

    message: str = last_message.content

    # Trích xuất tên món từ message (dùng Gemini flash)
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=0,
    )

    extract_response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Trích xuất TÊN MÓN ĂN từ câu hỏi. Chỉ trả về tên món, không thêm gì khác.\n"
                    "Ví dụ: 'Phở bò có bao nhiêu calo?' → 'phở bò'\n"
                    "Ví dụ: 'Tính calo của bún bò huế' → 'bún bò huế'"
                ),
            },
            {"role": "user", "content": message},
        ]
    )

    dish_name = (
        extract_response.content.strip().lower()
        if isinstance(extract_response.content, str)
        else ""
    )

    if not dish_name:
        return {
            "messages": [
                AIMessage(
                    content="❌ Không xác định được tên món. Vui lòng nói rõ tên món ăn."
                )
            ]
        }

    logger.info(f"[CalorieAgent] Looking up: '{dish_name}'")

    # 1. Local lookup
    local_data = _lookup_local(dish_name)
    if local_data:
        return {
            "messages": [
                AIMessage(
                    content=_format_calorie_response(dish_name, local_data, "local")
                )
            ]
        }

    # 2. DB lookup
    db_data = _lookup_db(dish_name)
    if db_data:
        return {
            "messages": [
                AIMessage(
                    content=_format_calorie_response(dish_name, db_data, "database")
                )
            ]
        }

    # 3. Gemini fallback
    logger.info(
        f"[CalorieAgent] Not found locally/DB, asking Gemini for: '{dish_name}'"
    )
    gemini_response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Bạn là chuyên gia dinh dưỡng. Ước tính calories và macros cho món ăn.\n"
                    'Trả về JSON format: {"calories": số, "protein": số, "carbs": số, "fat": số}\n'
                    "Đơn vị: kcal cho calories, gram cho protein/carbs/fat.\n"
                    "Tính cho 1 khẩu phần ăn bình thường của người Việt Nam."
                ),
            },
            {"role": "user", "content": f"Tính dinh dưỡng cho: {dish_name}"},
        ]
    )

    import json
    import re

    try:
        content = (
            gemini_response.content if isinstance(gemini_response.content, str) else ""
        )
        json_match = re.search(r"\{.*?\}", content, re.DOTALL)
        if json_match:
            nutrition = json.loads(json_match.group())
            return {
                "messages": [
                    AIMessage(
                        content=_format_calorie_response(dish_name, nutrition, "gemini")
                    )
                ]
            }
    except Exception as e:
        logger.error(f"[CalorieAgent] Gemini parse failed: {e}")

    return {
        "messages": [
            AIMessage(
                content=f"❌ Không tìm được thông tin dinh dưỡng cho **{dish_name}**. Vui lòng thử tên món khác."
            )
        ]
    }
