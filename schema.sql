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
    embedding VECTOR(3072) -- For RAG
);

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
