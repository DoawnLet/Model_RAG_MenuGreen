-- Menu Green database bootstrap
-- Use this for a fresh database setup.
--
-- Default vector dimension in this file is 3072 for Gemini embeddings.
-- If you switch the whole app to ONNX-only embeddings, you must also align:
--   1. recipes.embedding VECTOR(...)
--   2. match_recipes(query_embedding VECTOR(...))

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    name TEXT NOT NULL,
    age INT,
    gender TEXT CHECK (gender IN ('male', 'female', 'other')),
    height_cm NUMERIC,
    weight_kg NUMERIC,
    activity_level TEXT CHECK (activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')),
    goal TEXT CHECK (goal IN ('lose_fat', 'maintain', 'gain_muscle')),
    dietary_preferences TEXT[],
    allergies TEXT[]
);

CREATE TABLE IF NOT EXISTS ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    calories_per_100g NUMERIC NOT NULL,
    protein_per_100g NUMERIC NOT NULL,
    carbs_per_100g NUMERIC NOT NULL,
    fat_per_100g NUMERIC NOT NULL,
    fiber_per_100g NUMERIC DEFAULT 0,
    category TEXT
);

CREATE TABLE IF NOT EXISTS recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    prep_time_minutes INT,
    cook_time_minutes INT,
    servings INT,
    image_url TEXT,
    dietary_tags TEXT[],
    calories_per_serving NUMERIC,
    protein_per_serving NUMERIC,
    carbs_per_serving NUMERIC,
    fat_per_serving NUMERIC,
    embedding VECTOR(3072)
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id UUID REFERENCES ingredients(id) ON DELETE SET NULL,
    amount NUMERIC NOT NULL,
    unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    ingredient_id UUID REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity NUMERIC NOT NULL,
    unit TEXT,
    expiry_date DATE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    date DATE DEFAULT CURRENT_DATE,
    calories_consumed NUMERIC DEFAULT 0,
    protein_consumed NUMERIC DEFAULT 0,
    carbs_consumed NUMERIC DEFAULT 0,
    fat_consumed NUMERIC DEFAULT 0,
    water_ml INT DEFAULT 0,
    mood TEXT,
    energy_level INT CHECK (energy_level BETWEEN 1 AND 10),
    health_score INT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES user_profiles(id) ON DELETE CASCADE,
    tier TEXT NOT NULL CHECK (tier IN ('free', 'saving', 'energy', 'performance')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    nutrition_targets JSONB NOT NULL,
    preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meal_plan_meals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id UUID NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    serving_size NUMERIC DEFAULT 1.0,
    is_completed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id UUID NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    items JSONB NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN recipes.dietary_tags IS 'Dietary restriction tags: vegetarian, vegan, gluten_free, dairy_free, halal, kosher, keto, paleo, etc.';
COMMENT ON COLUMN recipes.calories_per_serving IS 'Calories per serving (kcal)';
COMMENT ON COLUMN recipes.protein_per_serving IS 'Protein per serving (grams)';
COMMENT ON COLUMN recipes.carbs_per_serving IS 'Carbohydrates per serving (grams)';
COMMENT ON COLUMN recipes.fat_per_serving IS 'Fat per serving (grams)';

COMMENT ON TABLE user_subscriptions IS 'User subscription tiers and status tracking';
COMMENT ON COLUMN user_subscriptions.tier IS 'Subscription tier: free, saving, energy, performance';
COMMENT ON COLUMN user_subscriptions.is_active IS 'Active if within expiry or tier is free';

COMMENT ON TABLE meal_plans IS 'User-generated meal plans with nutrition targets and preferences';
COMMENT ON COLUMN meal_plans.nutrition_targets IS 'Daily nutrition targets: {calories, protein, carbs, fat}';
COMMENT ON COLUMN meal_plans.preferences IS 'User preferences: {dietary_restrictions, allergies, cuisine_types}';

COMMENT ON TABLE meal_plan_meals IS 'Links meal plans to recipes for specific dates and meal types';
COMMENT ON COLUMN meal_plan_meals.serving_size IS 'Serving multiplier such as 1.5 servings';
COMMENT ON COLUMN meal_plan_meals.is_completed IS 'Whether user marked this meal as eaten';

COMMENT ON TABLE shopping_lists IS 'Shopping lists generated from meal plans';
COMMENT ON COLUMN shopping_lists.items IS 'Shopping items array: [{ingredient_id, name, quantity, unit, is_checked}]';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_plans_user_id ON meal_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_shopping_lists_user_id ON shopping_lists(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_inventory_user_ingredient_unique ON user_inventory(user_id, ingredient_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires_at ON user_subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_is_active ON user_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_meal_plans_status ON meal_plans(status);
CREATE INDEX IF NOT EXISTS idx_meal_plans_start_date ON meal_plans(start_date);
CREATE INDEX IF NOT EXISTS idx_meal_plans_end_date ON meal_plans(end_date);
CREATE INDEX IF NOT EXISTS idx_meal_plans_user_status ON meal_plans(user_id, status);
CREATE INDEX IF NOT EXISTS idx_meal_plan_meals_plan_id ON meal_plan_meals(meal_plan_id);
CREATE INDEX IF NOT EXISTS idx_meal_plan_meals_recipe_id ON meal_plan_meals(recipe_id);
CREATE INDEX IF NOT EXISTS idx_meal_plan_meals_date ON meal_plan_meals(date);
CREATE INDEX IF NOT EXISTS idx_meal_plan_meals_plan_date ON meal_plan_meals(meal_plan_id, date);
CREATE INDEX IF NOT EXISTS idx_shopping_lists_meal_plan_id ON shopping_lists(meal_plan_id);
CREATE INDEX IF NOT EXISTS idx_shopping_lists_status ON shopping_lists(status);
CREATE INDEX IF NOT EXISTS idx_recipes_name_search ON recipes USING gin(to_tsvector('simple', name));
-- pgvector cannot create a regular vector index above 2000 dims.
-- Use half-precision expression indexing for 3072D Gemini embeddings.
CREATE INDEX IF NOT EXISTS idx_recipes_embedding
    ON recipes
    USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);

-- ============================================================================
-- RAG RPC
-- ============================================================================

DROP FUNCTION IF EXISTS match_recipes(vector, double precision, integer);

CREATE OR REPLACE FUNCTION match_recipes(
    query_embedding VECTOR(3072),
    match_threshold DOUBLE PRECISION DEFAULT 0.5,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    description TEXT,
    prep_time_minutes INT,
    cook_time_minutes INT,
    servings INT,
    dietary_tags TEXT[],
    similarity DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        r.name,
        r.description,
        r.prep_time_minutes,
        r.cook_time_minutes,
        r.servings,
        r.dietary_tags,
        1 - ((r.embedding::halfvec(3072)) <=> (query_embedding::halfvec(3072))) AS similarity
    FROM recipes r
    WHERE r.embedding IS NOT NULL
      AND 1 - ((r.embedding::halfvec(3072)) <=> (query_embedding::halfvec(3072))) > match_threshold
    ORDER BY (r.embedding::halfvec(3072)) <=> (query_embedding::halfvec(3072))
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- LANGGRAPH CHECKPOINT TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BYTEA,
    metadata BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    value BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_plan_meals ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoint_writes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile" ON user_profiles FOR SELECT USING (auth.uid() = id);
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE USING (auth.uid() = id);
DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
CREATE POLICY "Users can insert own profile" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Ingredients are viewable by everyone" ON ingredients;
CREATE POLICY "Ingredients are viewable by everyone" ON ingredients FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can modify ingredients" ON ingredients;
CREATE POLICY "Only admins can modify ingredients" ON ingredients
    FOR ALL USING (
        (auth.jwt() ->> 'role')::text = 'admin'
        OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
    );

DROP POLICY IF EXISTS "Recipes are viewable by everyone" ON recipes;
CREATE POLICY "Recipes are viewable by everyone" ON recipes FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can insert recipes" ON recipes;
CREATE POLICY "Only admins can insert recipes" ON recipes
    FOR INSERT WITH CHECK (
        (auth.jwt() ->> 'role')::text = 'admin'
        OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
    );
DROP POLICY IF EXISTS "Only admins can update recipes" ON recipes;
CREATE POLICY "Only admins can update recipes" ON recipes
    FOR UPDATE USING (
        (auth.jwt() ->> 'role')::text = 'admin'
        OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
    );
DROP POLICY IF EXISTS "Only admins can delete recipes" ON recipes;
CREATE POLICY "Only admins can delete recipes" ON recipes
    FOR DELETE USING (
        (auth.jwt() ->> 'role')::text = 'admin'
        OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
    );

DROP POLICY IF EXISTS "Recipe ingredients are viewable by everyone" ON recipe_ingredients;
CREATE POLICY "Recipe ingredients are viewable by everyone" ON recipe_ingredients FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can modify recipe ingredients" ON recipe_ingredients;
CREATE POLICY "Only admins can modify recipe ingredients" ON recipe_ingredients
    FOR ALL USING (
        (auth.jwt() ->> 'role')::text = 'admin'
        OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
    );

DROP POLICY IF EXISTS "Users can view own inventory" ON user_inventory;
CREATE POLICY "Users can view own inventory" ON user_inventory FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own inventory" ON user_inventory;
CREATE POLICY "Users can insert own inventory" ON user_inventory FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own inventory" ON user_inventory;
CREATE POLICY "Users can update own inventory" ON user_inventory FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own inventory" ON user_inventory;
CREATE POLICY "Users can delete own inventory" ON user_inventory FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own logs" ON daily_logs;
CREATE POLICY "Users can view own logs" ON daily_logs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own logs" ON daily_logs;
CREATE POLICY "Users can insert own logs" ON daily_logs FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own logs" ON daily_logs;
CREATE POLICY "Users can update own logs" ON daily_logs FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own logs" ON daily_logs;
CREATE POLICY "Users can delete own logs" ON daily_logs FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS user_subscriptions_select ON user_subscriptions;
CREATE POLICY user_subscriptions_select ON user_subscriptions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS user_subscriptions_insert ON user_subscriptions;
CREATE POLICY user_subscriptions_insert ON user_subscriptions FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS user_subscriptions_update ON user_subscriptions;
CREATE POLICY user_subscriptions_update ON user_subscriptions FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS meal_plans_select ON meal_plans;
CREATE POLICY meal_plans_select ON meal_plans FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS meal_plans_insert ON meal_plans;
CREATE POLICY meal_plans_insert ON meal_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS meal_plans_update ON meal_plans;
CREATE POLICY meal_plans_update ON meal_plans FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS meal_plans_delete ON meal_plans;
CREATE POLICY meal_plans_delete ON meal_plans FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS meal_plan_meals_select ON meal_plan_meals;
CREATE POLICY meal_plan_meals_select ON meal_plan_meals
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
              AND meal_plans.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS meal_plan_meals_insert ON meal_plan_meals;
CREATE POLICY meal_plan_meals_insert ON meal_plan_meals
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1
            FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
              AND meal_plans.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS meal_plan_meals_update ON meal_plan_meals;
CREATE POLICY meal_plan_meals_update ON meal_plan_meals
    FOR UPDATE USING (
        EXISTS (
            SELECT 1
            FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
              AND meal_plans.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS meal_plan_meals_delete ON meal_plan_meals;
CREATE POLICY meal_plan_meals_delete ON meal_plan_meals
    FOR DELETE USING (
        EXISTS (
            SELECT 1
            FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
              AND meal_plans.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS shopping_lists_select ON shopping_lists;
CREATE POLICY shopping_lists_select ON shopping_lists FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS shopping_lists_insert ON shopping_lists;
CREATE POLICY shopping_lists_insert ON shopping_lists FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS shopping_lists_update ON shopping_lists;
CREATE POLICY shopping_lists_update ON shopping_lists FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS shopping_lists_delete ON shopping_lists;
CREATE POLICY shopping_lists_delete ON shopping_lists FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Allow all access to checkpoints" ON checkpoints;
CREATE POLICY "Allow all access to checkpoints" ON checkpoints FOR ALL USING (true);
DROP POLICY IF EXISTS "Allow all access to checkpoint_writes" ON checkpoint_writes;
CREATE POLICY "Allow all access to checkpoint_writes" ON checkpoint_writes FOR ALL USING (true);

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_subscriptions_updated_at ON user_subscriptions;
CREATE TRIGGER update_user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_meal_plans_updated_at ON meal_plans;
CREATE TRIGGER update_meal_plans_updated_at
    BEFORE UPDATE ON meal_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_shopping_lists_updated_at ON shopping_lists;
CREATE TRIGGER update_shopping_lists_updated_at
    BEFORE UPDATE ON shopping_lists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;
