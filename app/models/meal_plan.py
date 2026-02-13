"""
Pydantic models for 7-day meal planning system.
Defines data structures for nutrition targets, recipes, meal plans, and shopping lists.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import date


# ============================================================================
# Nutrition Target Models
# ============================================================================

class MealDistribution(BaseModel):
    """Phân bổ calories cho mỗi bữa ăn theo phần trăm."""
    breakfast_percent: float = Field(default=0.25, description="25% calo cho bữa sáng")
    lunch_percent: float = Field(default=0.35, description="35% calo cho bữa trưa")
    dinner_percent: float = Field(default=0.30, description="30% calo cho bữa tối")
    snack_percent: float = Field(default=0.10, description="10% calo cho bữa phụ")


class NutritionTargets(BaseModel):
    """
    Target dinh dưỡng hàng ngày + phân bổ bữa ăn.
    Được tính từ BMR/TDEE based on user profile.
    """
    daily_calories: float = Field(description="Tổng calories mục tiêu mỗi ngày")
    protein_g: float = Field(description="Lượng protein (grams) mỗi ngày")
    carbs_g: float = Field(description="Lượng carbs (grams) mỗi ngày")
    fat_g: float = Field(description="Lượng fat (grams) mỗi ngày")
    meal_distribution: MealDistribution = Field(default_factory=MealDistribution)

    def get_meal_targets(self, meal_type: Literal["breakfast", "lunch", "dinner", "snack"]) -> dict:
        """
        Tính target dinh dưỡng cho từng bữa cụ thể.

        Args:
            meal_type: Loại bữa ăn

        Returns:
            Dict chứa calories, protein_g, carbs_g, fat_g cho bữa đó
        """
        percent = getattr(self.meal_distribution, f"{meal_type}_percent")
        return {
            "calories": self.daily_calories * percent,
            "protein_g": self.protein_g * percent,
            "carbs_g": self.carbs_g * percent,
            "fat_g": self.fat_g * percent,
        }


# ============================================================================
# Recipe Models
# ============================================================================

class RecipeIngredient(BaseModel):
    """Nguyên liệu trong công thức với thông tin dinh dưỡng."""
    name: str = Field(description="Tên nguyên liệu tiếng Việt")
    amount: float = Field(description="Khối lượng/số lượng")
    unit: str = Field(description="Đơn vị (g, ml, quả, thìa, củ, ...)")
    calories: Optional[float] = Field(default=None, description="Calories của nguyên liệu này")
    protein: Optional[float] = Field(default=None, description="Protein (g) của nguyên liệu này")
    in_inventory: bool = Field(default=False, description="True nếu có sẵn trong kho")


class RecipeNutrition(BaseModel):
    """Thông tin dinh dưỡng tổng của món ăn."""
    calories: float = Field(description="Tổng calories")
    protein_g: float = Field(description="Tổng protein (grams)")
    carbs_g: float = Field(description="Tổng carbs (grams)")
    fat_g: float = Field(description="Tổng fat (grams)")
    fiber_g: Optional[float] = Field(default=0, description="Chất xơ (grams)")


class AdaptedRecipe(BaseModel):
    """
    Món ăn đã được adapt chi tiết tiếng Việt.
    Bao gồm nguyên liệu đã scaled, cách làm từng bước, và dinh dưỡng adjusted.
    """
    ten: str = Field(description="Tên món ăn tiếng Việt")
    thoi_gian_nau: int = Field(description="Thời gian nấu (phút)")
    nguyen_lieu: list[RecipeIngredient] = Field(description="Danh sách nguyên liệu")
    cach_lam: list[str] = Field(description="Các bước thực hiện (step-by-step)")
    dinh_duong: RecipeNutrition = Field(description="Thông tin dinh dưỡng")
    ghi_chu: Optional[str] = Field(default=None, description="Ghi chú thêm (tips, substitutions)")


# ============================================================================
# Meal Plan Models
# ============================================================================

class Meal(BaseModel):
    """Một bữa ăn trong ngày gồm loại bữa + món ăn chi tiết."""
    loai: Literal["sáng", "trưa", "tối", "phụ"] = Field(description="Loại bữa ăn")
    mon_an: AdaptedRecipe = Field(description="Chi tiết món ăn đã adapt")


class DailyMealPlan(BaseModel):
    """Thực đơn hoàn chỉnh cho 1 ngày."""
    ngay: int = Field(ge=1, le=7, description="Ngày trong tuần (1-7)")
    ngay_thuc: date = Field(description="Ngày thực tế (yyyy-mm-dd)")
    tong_calo: float = Field(description="Tổng calories trong ngày")
    buoi_an: list[Meal] = Field(description="Các bữa ăn trong ngày (4 bữa)")


    buoi_an: list[Meal] = Field(description="Các bữa ăn trong ngày (4 bữa)")


class SearchQueries(BaseModel):
    """Danh sách các truy vấn tìm kiếm."""
    queries: list[str] = Field(description="Danh sách 4 query tìm kiếm món ăn")


class DailyAllocation(BaseModel):
    """Phân bổ món ăn cho 1 ngày (chỉ chứa ID)."""
    breakfast: str = Field(description="Recipe ID cho bữa sáng")
    lunch: str = Field(description="Recipe ID cho bữa trưa")
    dinner: str = Field(description="Recipe ID cho bữa tối")
    snack: str = Field(description="Recipe ID cho bữa phụ")


class WeeklyMealPlanAllocation(BaseModel):
    """Phân bổ thực đơn cho 7 ngày."""
    allocations: list[DailyAllocation] = Field(description="Danh sách phân bổ cho 7 ngày", min_length=7, max_length=7)

class ShoppingListItem(BaseModel):
    """Một item trong danh sách mua sắm."""
    ten_nguyen_lieu: str = Field(description="Tên nguyên liệu")
    so_luong: float = Field(description="Số lượng cần mua")
    don_vi: str = Field(description="Đơn vị (kg, g, lít, mL, ...)")
    co_san_trong_kho: bool = Field(default=False, description="True nếu đã có sẵn")
    ghi_chu: Optional[str] = Field(default=None, description="Ghi chú (ví dụ: optional, có thể thay thế)")


# ============================================================================
# Output Models
# ============================================================================

class UserInfo(BaseModel):
    """Thông tin người dùng hiển thị trong output."""
    ten: str = Field(description="Tên người dùng")
    muc_tieu: str = Field(description="Mục tiêu (Giảm cân, Tăng cơ, Duy trì)")
    calo_ngay: float = Field(description="Target calories mỗi ngày")
    protein_g: float = Field(description="Target protein (g) mỗi ngày")


class MealPlanOutput(BaseModel):
    """
    Complete meal plan output theo format yêu cầu.

    Đây là output chính được trả về từ meal planning workflow,
    bao gồm thực đơn 7 ngày + shopping list + metadata.
    """
    thong_tin_nguoi_dung: UserInfo = Field(description="Thông tin và mục tiêu người dùng")
    thuc_don_7_ngay: list[DailyMealPlan] = Field(description="Thực đơn 7 ngày (28 bữa)")
    danh_sach_mua: list[ShoppingListItem] = Field(description="Danh sách nguyên liệu cần mua")
    ghi_chu: str = Field(description="Ghi chú tổng quan về thực đơn")

    class Config:
        json_schema_extra = {
            "example": {
                "thong_tin_nguoi_dung": {
                    "ten": "Nguyễn Văn A",
                    "muc_tieu": "Tăng cơ",
                    "calo_ngay": 2200,
                    "protein_g": 165
                },
                "thuc_don_7_ngay": [
                    {
                        "ngay": 1,
                        "ngay_thuc": "2026-02-12",
                        "tong_calo": 2180,
                        "buoi_an": [
                            {
                                "loai": "sáng",
                                "mon_an": {
                                    "ten": "Yến mạch chuối và hạt chia",
                                    "thoi_gian_nau": 10,
                                    "nguyen_lieu": [
                                        {"name": "Yến mạch", "amount": 50, "unit": "g", "in_inventory": True}
                                    ],
                                    "cach_lam": ["Bước 1: Đun sôi 200ml sữa"],
                                    "dinh_duong": {"calories": 320, "protein_g": 15, "carbs_g": 45, "fat_g": 8}
                                }
                            }
                        ]
                    }
                ],
                "danh_sach_mua": [
                    {"ten_nguyen_lieu": "Ức gà", "so_luong": 1.5, "don_vi": "kg", "co_san_trong_kho": False}
                ],
                "ghi_chu": "Thực đơn được tối ưu hoàn chỉnh!"
            }
        }
