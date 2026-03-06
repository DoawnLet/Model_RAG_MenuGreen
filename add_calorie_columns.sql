-- ============================================================
-- Migration: Add calorie columns to recipes table
-- Chạy trong Supabase SQL Editor
-- ============================================================

-- Thêm cột calo vào bảng recipes
ALTER TABLE recipes
    ADD COLUMN IF NOT EXISTS calories_per_serving  NUMERIC,
    ADD COLUMN IF NOT EXISTS protein_per_serving   NUMERIC,
    ADD COLUMN IF NOT EXISTS carbs_per_serving     NUMERIC,
    ADD COLUMN IF NOT EXISTS fat_per_serving       NUMERIC;

COMMENT ON COLUMN recipes.calories_per_serving IS 'Calories per serving (kcal)';
COMMENT ON COLUMN recipes.protein_per_serving  IS 'Protein per serving (grams)';
COMMENT ON COLUMN recipes.carbs_per_serving    IS 'Carbohydrates per serving (grams)';
COMMENT ON COLUMN recipes.fat_per_serving      IS 'Fat per serving (grams)';

-- Index để tìm kiếm theo tên món nhanh hơn
CREATE INDEX IF NOT EXISTS idx_recipes_name_search
    ON recipes USING gin(to_tsvector('simple', name));

-- Ví dụ: Update calo cho một số món mẫu (nếu có data)
-- UPDATE recipes SET calories_per_serving = 450 WHERE name ILIKE '%phở bò%';
-- UPDATE recipes SET calories_per_serving = 380 WHERE name ILIKE '%phở gà%';
