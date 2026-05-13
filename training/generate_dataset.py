"""
Generate a compact but practical training dataset for the Menu Green
intent classifier.

Run:
    python -X utf8 training/generate_dataset.py

Output:
    training/intent_dataset.json
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict


LABEL_ORDER = [
    "recipe_search",
    "nutrition_calc",
    "inventory_check",
    "meal_plan",
    "web_browsing",
    "calorie_lookup",
    "general",
    "unknown",
]

LABEL_MAP = {name: index for index, name in enumerate(LABEL_ORDER)}


DATASET = {
    "recipe_search": [
        "Tìm món ăn từ cà chua và trứng",
        "Món gì ngon cho bữa trưa?",
        "Cách làm phở bò",
        "Gợi ý món ăn với gà",
        "Tôi muốn nấu bún bò Huế",
        "Có công thức cơm rang không?",
        "Món chay nào ngon?",
        "Cách làm bánh mì thịt",
        "Tìm công thức salad thanh mát",
        "Món nào nấu nhanh dưới 30 phút?",
        "Gợi ý món ăn với hải sản",
        "Cách làm canh chua cá",
        "Tôi có thịt heo muốn nấu gì?",
        "Món ăn giảm cân ngon",
        "Công thức làm smoothie hoa quả",
        "Cách làm chả giò ngon",
        "Tìm món ăn cho trẻ em",
        "Gợi ý món tráng miệng",
        "Nấu súp gà kiểu gì?",
        "Món ăn sáng nhanh và bổ dưỡng",
        "Có công thức nấu lẩu không?",
        "Cách làm gỏi cuốn",
        "What can I cook with chicken and vegetables?",
        "Suggest a quick dinner recipe",
        "How to make pho from scratch?",
        "Easy Vietnamese recipes",
        "Healthy meal ideas for lunch",
        "Recipe with tofu and mushroom",
        "How to cook banh mi?",
        "Vegetarian dishes suggestions",
        "Món ăn từ rau củ",
        "Tìm recipe với đậu hũ",
        "Cách làm mì xào",
        "Gợi ý món nướng BBQ",
        "Cơm tấm làm như thế nào?",
        "Tìm công thức lẩu thái",
        "Nấu bò kho ra sao?",
        "Gợi ý món từ tôm",
        "Find me a recipe with eggs",
        "Simple soup recipe",
    ],
    "nutrition_calc": [
        "Tính BMR cho tôi",
        "TDEE của tôi là bao nhiêu?",
        "Tôi cần bao nhiêu protein mỗi ngày?",
        "Tính lượng calo cần thiết",
        "Macro của tôi nên như thế nào?",
        "Tôi nặng 70kg cao 1m70 cần ăn bao nhiêu?",
        "Tính nhu cầu dinh dưỡng hàng ngày",
        "Tôi muốn giảm 5kg cần ăn bao nhiêu calo?",
        "Lượng carb tôi cần nạp mỗi ngày?",
        "Phân tích dinh dưỡng cá nhân",
        "Calculate my BMR",
        "What is my daily calorie need?",
        "How much protein should I eat?",
        "Calculate TDEE for weight loss",
        "My macros for muscle building",
        "Tôi cần bao nhiêu chất béo mỗi ngày?",
        "Tính calories mục tiêu để tăng cơ",
        "Chỉ số BMI của tôi?",
        "Tôi cần uống bao nhiêu nước mỗi ngày?",
        "Daily nutrition requirements for my profile",
        "Fat intake recommendation for me",
        "How many calories to lose weight?",
        "Protein requirement for athletes",
        "Tính mức calo duy trì cho nam 25 tuổi",
        "Tính giúp tôi lượng protein theo cân nặng",
    ],
    "inventory_check": [
        "Nguyên liệu nào sắp hết hạn?",
        "Kiểm tra tủ lạnh của tôi",
        "Còn gì trong kho nguyên liệu?",
        "Nguyên liệu nào cần mua thêm?",
        "Hạn sử dụng của sữa?",
        "Tôi còn bao nhiêu thịt trong tủ?",
        "Kiểm tra inventory",
        "Rau củ nào sắp hỏng?",
        "Cập nhật kho nguyên liệu",
        "Check my pantry",
        "What's in my fridge?",
        "Ingredients expiring soon",
        "Update my inventory",
        "What groceries do I need?",
        "Check expiry dates",
        "Tủ lạnh còn gì?",
        "Nguyên liệu nào còn nhiều?",
        "Cần mua gì tuần này?",
        "Thức ăn nào gần hết hạn?",
        "Báo cáo tồn kho",
        "Xem giúp tôi đồ ăn nào sắp hư",
        "Kiểm tra xem còn trứng hay không",
        "Trong kho còn bao nhiêu gạo",
        "Danh sách nguyên liệu còn lại là gì",
        "Fridge check for expiring items",
        "Pantry status today",
    ],
    "meal_plan": [
        "Lên thực đơn tuần cho tôi",
        "Kế hoạch ăn 7 ngày giảm cân",
        "Meal prep cho 1 tuần",
        "Lập thực đơn dinh dưỡng",
        "Tạo kế hoạch bữa ăn hàng tuần",
        "Thực đơn giảm cân 1 tuần",
        "Lên menu tuần cho gia đình",
        "Create a 7-day meal plan",
        "Weekly meal planning for weight loss",
        "Meal prep ideas for the week",
        "Plan my meals for this week",
        "Generate a healthy meal plan",
        "Kế hoạch eat clean 7 ngày",
        "Thực đơn Keto 1 tuần",
        "Lên menu cho người tiểu đường",
        "Meal plan để tăng cơ",
        "Thực đơn cho vận động viên",
        "Lập kế hoạch ăn uống khoa học",
        "Weekly diet plan suggestion",
        "Create a balanced meal schedule",
        "Lập thực đơn 3 ngày từ nguyên liệu sẵn có",
        "Tạo menu giảm mỡ cho nữ văn phòng",
        "Thực đơn theo ngân sách 1 tuần",
    ],
    "web_browsing": [
        "https://cookpad.com/vn/recipe/123456",
        "Đọc bài này giúp tôi: https://beptruong.edu.vn/mon-an/pho-bo",
        "Tóm tắt link này https://giaoducyte.vn/dinh-duong",
        "https://www.allrecipes.com/recipe/234567",
        "Lấy công thức từ https://yummly.com/recipe/sample",
        "Read this recipe: https://tasty.co/recipe/chicken-soup",
        "Summarize https://healthline.com/nutrition/protein",
        "Crawl nội dung từ link: https://cookpad.com",
        "https://baomoi.com/dinh-duong-va-suc-khoe",
        "Xem công thức tại url này: https://monngonmoingay.com",
        "https://www.bbcgoodfood.com/recipes/breakfast",
        "Tóm tắt nội dung https://vinmec.com/vi/dinh-duong",
        "Get recipe from https://recipetineats.com",
        "https://www.seriouseats.com/recipes",
        "Mở link này và đọc giúp tôi https://example.com/recipe",
        "Check this article https://example.org/nutrition",
    ],
    "calorie_lookup": [
        "Phở bò bao nhiêu calo?",
        "Bún bò có bao nhiêu protein?",
        "Tính calo cơm tấm",
        "1 tô hủ tiếu bao nhiêu kcal?",
        "Calo trong bánh mì thịt là bao nhiêu?",
        "Món này có bao nhiêu chất béo?",
        "Lượng protein của ức gà luộc",
        "Một ly sinh tố xoài có bao nhiêu calo?",
        "Calories in fried rice",
        "How many calories are in pho?",
        "Nutrition facts for banh mi",
        "Cơm gà xối mỡ bao nhiêu calo",
        "100g đậu hũ có bao nhiêu protein",
        "Bánh flan có bao nhiêu đường",
        "Tính dinh dưỡng của salad cá ngừ",
        "Lẩu thái có nhiều calo không",
        "Một quả trứng bao nhiêu calo",
        "Calo của trà sữa là bao nhiêu",
        "Protein trong bò bít tết",
        "Nutritional value of spring rolls",
    ],
    "general": [
        "Ăn gì để tăng cơ?",
        "Chế độ ăn cho người tiểu đường",
        "Lợi ích của rau xanh là gì?",
        "Tại sao nên ăn sáng?",
        "Thực phẩm tốt cho não bộ",
        "Omega-3 có trong thực phẩm nào?",
        "Cách ăn uống lành mạnh",
        "Lợi ích của việc uống đủ nước",
        "Thực phẩm giúp ngủ ngon",
        "Ăn uống đúng cách khi tập gym",
        "Tips for healthy eating",
        "Benefits of eating vegetables",
        "Foods that boost immune system",
        "How to maintain a balanced diet?",
        "Good foods for skin health",
        "Thực phẩm nào giàu sắt?",
        "Vitamin D có trong đâu?",
        "Cách bổ sung canxi tự nhiên",
        "Ăn gì tốt cho tim mạch?",
        "Thực phẩm chống oxy hóa tốt nhất",
        "Tại sao không nên bỏ bữa?",
        "Cách kiểm soát đường huyết qua ăn uống",
        "Thực phẩm giúp giảm stress",
        "Lợi ích của probiotics",
        "Ăn chay có đủ dinh dưỡng không?",
        "Menu Green là gì?",
        "Bạn có thể giúp gì cho tôi?",
        "Xin chào",
        "Tôi muốn sống khỏe hơn",
        "Lời khuyên dinh dưỡng tổng quát",
    ],
    "unknown": [
        "Thời tiết hôm nay thế nào?",
        "Ai thắng World Cup 2022?",
        "Giá vàng hôm nay",
        "Đặt vé máy bay đi Đà Nẵng",
        "Chơi game gì hay?",
        "Code Python làm sao?",
        "Phim hay nên xem",
        "News hôm nay có gì mới?",
        "Tỉ giá đô la",
        "Xem bói",
        "Who won the last election?",
        "What is the stock price?",
        "Tell me a joke",
        "How to learn programming?",
        "Weather forecast tomorrow",
        "Đường đi đến bệnh viện Bạch Mai",
        "Số điện thoại của ai đó",
        "2 + 2 = mấy?",
        "Dịch tiếng Nhật sang tiếng Việt",
        "Tìm nhà trọ giá rẻ",
        "Mở nhạc giúp tôi",
        "Lịch thi đấu bóng đá hôm nay",
        "Viết email xin nghỉ phép",
        "Sửa lỗi wifi như thế nào",
        "Tạo code C# đăng nhập",
        "How to center a div in CSS?",
        "Mua laptop nào tốt",
        "Bảng giá chứng khoán",
    ],
}


def _stratified_split(samples: list[dict], val_ratio: float = 0.2, seed: int = 42):
    """Keep label distribution stable across train/validation."""
    rng = random.Random(seed)
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample["label_name"]].append(sample)

    train: list[dict] = []
    val: list[dict] = []

    for label_name, label_samples in grouped.items():
        rng.shuffle(label_samples)
        val_count = max(1, round(len(label_samples) * val_ratio))
        val.extend(label_samples[:val_count])
        train.extend(label_samples[val_count:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def generate_dataset(output_path: str = "training/intent_dataset.json"):
    """Generate a clean JSON dataset with stratified train/val split."""
    samples = []

    for label_name in LABEL_ORDER:
        texts = DATASET[label_name]
        for text in texts:
            samples.append(
                {
                    "text": text.strip(),
                    "label": LABEL_MAP[label_name],
                    "label_name": label_name,
                }
            )

    train, val = _stratified_split(samples, val_ratio=0.2, seed=42)

    result = {
        "train": train,
        "val": val,
        "label_map": LABEL_MAP,
        "label_order": LABEL_ORDER,
        "num_labels": len(LABEL_ORDER),
        "total": len(samples),
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"Dataset generated: {len(samples)} samples")
    print(f"  Train: {len(train)} | Val: {len(val)}")
    print(f"  Labels: {LABEL_ORDER}")

    total_counts = Counter(sample["label_name"] for sample in samples)
    train_counts = Counter(sample["label_name"] for sample in train)
    val_counts = Counter(sample["label_name"] for sample in val)

    print("\nPer-class counts:")
    for label_name in LABEL_ORDER:
        print(
            f"  {label_name:<20} total={total_counts[label_name]:<3} "
            f"train={train_counts[label_name]:<3} val={val_counts[label_name]:<3}"
        )

    print(f"\nSaved to: {output_path}")
    return result


if __name__ == "__main__":
    os.makedirs("training", exist_ok=True)
    generate_dataset()
