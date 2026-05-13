-- Enable pgvector extension for RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- User Profiles Table
CREATE TABLE user_profiles (
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
    dietary_preferences TEXT[], -- e.g., ['vegan', 'gluten_free']
    allergies TEXT[]
);

-- Ingredients Table (Master List)
CREATE TABLE ingredients (  
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    calories_per_100g NUMERIC NOT NULL,
    protein_per_100g NUMERIC NOT NULL,
    carbs_per_100g NUMERIC NOT NULL,
    fat_per_100g NUMERIC NOT NULL,
    fiber_per_100g NUMERIC DEFAULT 0,
    category TEXT
);

-- Recipes Table
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    prep_time_minutes INT,
    cook_time_minutes INT,
    servings INT,
    image_url TEXT,
    dietary_tags TEXT[], -- P1 Feature: Array of dietary restriction tags (vegetarian, vegan, gluten_free, halal, etc.)
    embedding VECTOR(3072) -- For RAG with Gemini Embedding-001 (3072D)
);

COMMENT ON COLUMN recipes.dietary_tags IS 'Dietary restriction tags: vegetarian, vegan, gluten_free, dairy_free, halal, kosher, keto, paleo, etc.';

-- Recipe Ingredients (Join Table)
CREATE TABLE recipe_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID REFERENCES recipes(id) On DELETE CASCADE,
    ingredient_id UUID REFERENCES ingredients(id) ON DELETE SET NULL,
    amount NUMERIC NOT NULL,
    unit TEXT NOT NULL -- e.g., 'g', 'ml', 'pcs'
);

-- User Inventory (Pantry)
CREATE TABLE user_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    ingredient_id UUID REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity NUMERIC NOT NULL,
    unit TEXT,
    expiry_date DATE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily Logs / Health Score
CREATE TABLE daily_logs (
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
    health_score INT, -- Calculated daily score
    notes TEXT
);
-- =====================================================
-- USER SUBSCRIPTIONS TABLE
-- =====================================================
-- Tracks user subscription tiers and activation status
-- Relationship: 1:1 with user_profiles (one subscription per user)
CREATE TABLE user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES user_profiles(id) ON DELETE CASCADE,
    tier TEXT NOT NULL CHECK (tier IN ('free', 'saving', 'energy', 'performance')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE user_subscriptions IS 'User subscription tiers and status tracking';
COMMENT ON COLUMN user_subscriptions.tier IS 'Subscription tier: free (basic AI), saving (basic + budget), energy (+ energy), performance (+ performance)';
COMMENT ON COLUMN user_subscriptions.is_active IS 'Active if within expiry or tier is free';

-- =====================================================
-- MEAL PLANS TABLE
-- =====================================================
-- Stores generated meal plans for users
-- Relationship: 1:N with user_profiles (one user can have many meal plans)
CREATE TABLE meal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    nutrition_targets JSONB NOT NULL, -- {calories, protein, carbs, fat}
    preferences JSONB, -- {dietary_restrictions, allergies, cuisine_types}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE meal_plans IS 'User-generated meal plans with nutrition targets and preferences';
COMMENT ON COLUMN meal_plans.nutrition_targets IS 'Daily nutrition targets: {calories, protein, carbs, fat}';
COMMENT ON COLUMN meal_plans.preferences IS 'User preferences: {dietary_restrictions, allergies, cuisine_types}';

-- =====================================================
-- MEAL PLAN MEALS TABLE (Junction Table)
-- =====================================================
-- Links meal plans to specific recipes for each day and meal type
-- Relationship: N:M between meal_plans and recipes
CREATE TABLE meal_plan_meals (
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

COMMENT ON TABLE meal_plan_meals IS 'Junction table linking meal plans to recipes for specific dates and meal types';
COMMENT ON COLUMN meal_plan_meals.serving_size IS 'Serving multiplier (e.g., 1.5 for 1.5 servings)';
COMMENT ON COLUMN meal_plan_meals.is_completed IS 'Whether user marked this meal as eaten';

-- =====================================================
-- SHOPPING LISTS TABLE
-- =====================================================
-- Auto-generated shopping lists from meal plans
-- Relationship: 1:N with meal_plans (one meal plan can generate one shopping list)
CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id UUID NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    items JSONB NOT NULL, -- [{ingredient_id, name, quantity, unit, is_checked}]
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE shopping_lists IS 'Shopping lists generated from meal plans';
COMMENT ON COLUMN shopping_lists.items IS 'Shopping items: [{ingredient_id, name, quantity, unit, is_checked}]';

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- User lookups (frequent queries by user_id)
CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_meal_plans_user_id ON meal_plans(user_id);
CREATE INDEX idx_shopping_lists_user_id ON shopping_lists(user_id);

-- Subscription queries (check expiry, filter by active)
CREATE INDEX idx_user_subscriptions_expires_at ON user_subscriptions(expires_at);
CREATE INDEX idx_user_subscriptions_is_active ON user_subscriptions(is_active);

-- Meal plan queries (find active plans, date ranges)
CREATE INDEX idx_meal_plans_status ON meal_plans(status);
CREATE INDEX idx_meal_plans_start_date ON meal_plans(start_date);
CREATE INDEX idx_meal_plans_end_date ON meal_plans(end_date);
CREATE INDEX idx_meal_plans_user_status ON meal_plans(user_id, status); -- Composite index

-- Meal plan meals queries (find meals by plan, date, type)
CREATE INDEX idx_meal_plan_meals_plan_id ON meal_plan_meals(meal_plan_id);
CREATE INDEX idx_meal_plan_meals_recipe_id ON meal_plan_meals(recipe_id);
CREATE INDEX idx_meal_plan_meals_date ON meal_plan_meals(date);
CREATE INDEX idx_meal_plan_meals_plan_date ON meal_plan_meals(meal_plan_id, date); -- Composite index

-- Shopping list queries (find by meal plan, user)
CREATE INDEX idx_shopping_lists_meal_plan_id ON shopping_lists(meal_plan_id);
CREATE INDEX idx_shopping_lists_status ON shopping_lists(status);

-- Vector similarity search (CRITICAL for RAG performance)
-- For 3072D embeddings, use half-precision expression indexing.
CREATE INDEX idx_recipes_embedding
    ON recipes
    USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================

-- Enable RLS on all user-scoped tables
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_plan_meals ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;

-- User Subscriptions: Users can only access their own subscription
CREATE POLICY user_subscriptions_select ON user_subscriptions
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY user_subscriptions_insert ON user_subscriptions
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY user_subscriptions_update ON user_subscriptions
    FOR UPDATE
    USING (auth.uid() = user_id);

-- Meal Plans: Users can only access their own meal plans
CREATE POLICY meal_plans_select ON meal_plans
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY meal_plans_insert ON meal_plans
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY meal_plans_update ON meal_plans
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY meal_plans_delete ON meal_plans
    FOR DELETE
    USING (auth.uid() = user_id);

-- Meal Plan Meals: Users can only access meals from their own meal plans
CREATE POLICY meal_plan_meals_select ON meal_plan_meals
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
            AND meal_plans.user_id = auth.uid()
        )
    );

CREATE POLICY meal_plan_meals_insert ON meal_plan_meals
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
            AND meal_plans.user_id = auth.uid()
        )
    );

CREATE POLICY meal_plan_meals_update ON meal_plan_meals
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
            AND meal_plans.user_id = auth.uid()
        )
    );

CREATE POLICY meal_plan_meals_delete ON meal_plan_meals
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM meal_plans
            WHERE meal_plans.id = meal_plan_meals.meal_plan_id
            AND meal_plans.user_id = auth.uid()
        )
    );

-- Shopping Lists: Users can only access their own shopping lists
CREATE POLICY shopping_lists_select ON shopping_lists
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY shopping_lists_insert ON shopping_lists
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY shopping_lists_update ON shopping_lists
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY shopping_lists_delete ON shopping_lists
    FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- ADDITIONAL RLS POLICIES FOR PRODUCTION
-- ============================================================

-- User Profiles
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile" ON user_profiles FOR SELECT USING (auth.uid() = id);
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE USING (auth.uid() = id);
DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
CREATE POLICY "Users can insert own profile" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- User Inventory
DROP POLICY IF EXISTS "Users can view own inventory" ON user_inventory;
CREATE POLICY "Users can view own inventory" ON user_inventory FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own inventory" ON user_inventory;
CREATE POLICY "Users can insert own inventory" ON user_inventory FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own inventory" ON user_inventory;
CREATE POLICY "Users can update own inventory" ON user_inventory FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own inventory" ON user_inventory;
CREATE POLICY "Users can delete own inventory" ON user_inventory FOR DELETE USING (auth.uid() = user_id);

-- Daily Logs
DROP POLICY IF EXISTS "Users can view own logs" ON daily_logs;
CREATE POLICY "Users can view own logs" ON daily_logs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own logs" ON daily_logs;
CREATE POLICY "Users can insert own logs" ON daily_logs FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own logs" ON daily_logs;
CREATE POLICY "Users can update own logs" ON daily_logs FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own logs" ON daily_logs;
CREATE POLICY "Users can delete own logs" ON daily_logs FOR DELETE USING (auth.uid() = user_id);

-- Recipes
DROP POLICY IF EXISTS "Recipes are viewable by everyone" ON recipes;
CREATE POLICY "Recipes are viewable by everyone" ON recipes FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can insert recipes" ON recipes;
CREATE POLICY "Only admins can insert recipes" ON recipes FOR INSERT WITH CHECK ((auth.jwt() ->> 'role')::text = 'admin' OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin');
DROP POLICY IF EXISTS "Only admins can update recipes" ON recipes;
CREATE POLICY "Only admins can update recipes" ON recipes FOR UPDATE USING ((auth.jwt() ->> 'role')::text = 'admin' OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin');
DROP POLICY IF EXISTS "Only admins can delete recipes" ON recipes;
CREATE POLICY "Only admins can delete recipes" ON recipes FOR DELETE USING ((auth.jwt() ->> 'role')::text = 'admin' OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin');

-- Recipe Ingredients
DROP POLICY IF EXISTS "Recipe ingredients are viewable by everyone" ON recipe_ingredients;
CREATE POLICY "Recipe ingredients are viewable by everyone" ON recipe_ingredients FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can modify recipe ingredients" ON recipe_ingredients;
CREATE POLICY "Only admins can modify recipe ingredients" ON recipe_ingredients FOR ALL USING ((auth.jwt() ->> 'role')::text = 'admin' OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin');

-- Ingredients
DROP POLICY IF EXISTS "Ingredients are viewable by everyone" ON ingredients;
CREATE POLICY "Ingredients are viewable by everyone" ON ingredients FOR SELECT USING (true);
DROP POLICY IF EXISTS "Only admins can modify ingredients" ON ingredients;
CREATE POLICY "Only admins can modify ingredients" ON ingredients FOR ALL USING ((auth.jwt() ->> 'role')::text = 'admin' OR (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin');

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- =====================================================
-- TRIGGERS FOR AUTOMATIC UPDATED_AT
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at column
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_meal_plans_updated_at
    BEFORE UPDATE ON meal_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shopping_lists_updated_at
    BEFORE UPDATE ON shopping_lists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();    python -m app.main
