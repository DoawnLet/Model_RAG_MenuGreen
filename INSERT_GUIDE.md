# 📚 Hướng Dẫn Insert Data Vào Database Menu Green

## 🎯 Thứ tự Insert (Tuân theo Foreign Key Dependencies)

### Phase 1️⃣: Base Tables (Không có dependencies)

```
1. user_profiles       → Người dùng
2. ingredients         → Nguyên liệu
3. recipes             → Công thức nấu ăn
```

### Phase 2️⃣: First Level Dependencies

```
4. user_subscriptions  → Gói đăng ký (cần user_profiles)
5. recipe_ingredients  → Nguyên liệu trong công thức (cần recipes + ingredients)
6. user_inventory      → Kho nguyên liệu của user (cần user_profiles + ingredients)
```

### Phase 3️⃣: Meal Planning

```
7. meal_plans          → Kế hoạch ăn uống (cần user_profiles)
```

### Phase 4️⃣: Second Level Dependencies

```
8. meal_plan_meals     → Chi tiết bữa ăn (cần meal_plans + recipes)
9. shopping_lists      → Danh sách đi chợ (cần meal_plans + user_profiles)
10. daily_logs         → Nhật ký hàng ngày (cần user_profiles)
```

---

## ⚠️ Điều Kiện Tiên Quyết

### 1. Fix Database Schema
Chạy các lệnh SQL này trong **Supabase SQL Editor** trước:

```sql
-- Fix 1: Update embedding dimension
DROP INDEX IF EXISTS idx_recipes_embedding;
ALTER TABLE recipes ALTER COLUMN embedding TYPE VECTOR(3072);
CREATE INDEX idx_recipes_embedding ON recipes 
USING ivfflat (embedding vector_l2_ops) WITH (lists = 50);

-- Fix 2: Disable RLS cho development
ALTER TABLE recipes DISABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients DISABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_ingredients DISABLE ROW LEVEL SECURITY;
```

Hoặc chạy toàn bộ file: **`schema_fixes.sql`**

---

## 🚀 Cách Sử Dụng

### Option 1: Chạy Script Tự Động (Khuyến nghị)

```bash
python insert_data_guide.py
```

Script này sẽ:
- ✅ Insert data mẫu theo đúng thứ tự
- ✅ Tự động lấy IDs để link giữa các tables
- ✅ Hiển thị progress và errors
- ✅ Tổng kết kết quả

### Option 2: Insert Thủ Công (Qua Supabase Dashboard)

#### Bước 1: Insert User Profile
```sql
INSERT INTO user_profiles (name, age, gender, height_cm, weight_kg, activity_level, goal)
VALUES ('Nguyễn Văn An', 28, 'male', 175, 70, 'moderate', 'maintain')
RETURNING id;
```
→ Lưu lại `user_id`

#### Bước 2: Insert Ingredients
```sql
INSERT INTO ingredients (name, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, category)
VALUES 
('Thịt bò', 250, 26, 0, 15, 'Thịt'),
('Gạo', 130, 2.7, 28, 0.3, 'Tinh bột')
RETURNING id;
```
→ Lưu lại `ingredient_ids`

#### Bước 3: Insert Recipe
```sql
INSERT INTO recipes (name, description, instructions, prep_time_minutes, cook_time_minutes, servings, dietary_tags)
VALUES (
    'Phở Bò',
    'Phở bò Hà Nội truyền thống',
    '1. Luộc xương\n2. Nấu nước dùng\n3. Trụng bánh phở\n4. Bày món',
    30,
    120,
    4,
    ARRAY['high-protein', 'warming']
)
RETURNING id;
```
→ Lưu lại `recipe_id`

#### Bước 4: Insert User Subscription
```sql
INSERT INTO user_subscriptions (user_id, tier, is_active)
VALUES ('<user_id>', 'free', true);
```
→ Thay `<user_id>` bằng ID từ Bước 1

#### Bước 5: Insert Recipe Ingredients
```sql
INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount, unit)
VALUES 
('<recipe_id>', '<beef_id>', 300, 'g'),
('<recipe_id>', '<rice_id>', 200, 'g');
```
→ Link recipe với ingredients

#### Bước 6+: Tương tự cho các bảng còn lại...

---

## 🔍 Kiểm Tra Kết Quả

### Sau khi insert, chạy các lệnh này:

```bash
# Kiểm tra số lượng recipes
python check_data.py

# Hoặc chạy SQL query:
```

```sql
-- Đếm số records trong mỗi table
SELECT 'user_profiles' as table_name, COUNT(*) as count FROM user_profiles
UNION ALL
SELECT 'ingredients', COUNT(*) FROM ingredients
UNION ALL
SELECT 'recipes', COUNT(*) FROM recipes
UNION ALL
SELECT 'user_subscriptions', COUNT(*) FROM user_subscriptions
UNION ALL
SELECT 'recipe_ingredients', COUNT(*) FROM recipe_ingredients
UNION ALL
SELECT 'meal_plans', COUNT(*) FROM meal_plans;
```



---

## 💡 Tips & Best Practices

### 1. **Testing với dữ liệu nhỏ trước**
- Insert 1-2 records mỗi table để test
- Verify relationships hoạt động đúng
- Sau đó mới insert bulk data

### 2. **Sử dụng Transactions**
```python
# Trong Python
with supabase.transaction():
    # Insert related data
    # Rollback nếu có lỗi
```

### 3. **Xử lý Errors**
- Save IDs sau mỗi insert thành công
- Log errors để debug
- Có backup data trước khi insert lớn

### 4. **Foreign Key Constraints**
- Luôn insert parent records trước child records
- Check foreign key tồn tại trước khi insert
- Sử dụng `RETURNING id` để lấy IDs

---

## 📊 Data Relationships

```
user_profiles
├── user_subscriptions
├── user_inventory ──┐
├── meal_plans       │
│   ├── meal_plan_meals ──┐
│   └── shopping_lists    │
└── daily_logs            │
                          │
ingredients ──────────────┤
                          │
recipes ──────────────────┘
    └── recipe_ingredients
```

---

## 🐛 Troubleshooting

### Lỗi: "violates foreign key constraint"
➡️ **Nguyên nhân**: Insert child record trước parent record  
➡️ **Giải pháp**: Kiểm tra thứ tự insert, verify parent ID tồn tại

### Lỗi: "violates row-level security policy"
➡️ **Nguyên nhân**: RLS chưa được fix  
➡️ **Giải pháp**: Chạy `schema_fixes.sql` để disable RLS

### Lỗi: "embedding dimension mismatch"
➡️ **Nguyên nhân**: Schema vẫn dùng VECTOR(768)  
➡️ **Giải pháp**: Alter column thành VECTOR(3072)

### Lỗi: "duplicate key value"
➡️ **Nguyên nhân**: Insert record với ID/name đã tồn tại  
➡️ **Giải pháp**: Dùng UPSERT hoặc check tồn tại trước

---

## 📞 Support

Nếu gặp vấn đề:
1. Check logs trong terminal
2. Xem errors trong Supabase Dashboard → Logs
3. Verify schema với `schema_fixes.sql`
4. Run verification queries ở trên

---

## ✅ Checklist Hoàn Chỉnh

- [ ] Đã chạy `schema_fixes.sql`
- [ ] RLS đã được disable hoặc có policies đúng
- [ ] Embedding dimension là 3072
- [ ] Đã test insert 1 record mỗi table
- [ ] Verify foreign keys hoạt động
- [ ] Chạy `insert_data_guide.py` thành công
- [ ] Check data với `check_data.py`
- [ ] Tất cả 10 tables có data

---

**Happy inserting! 🎉**


