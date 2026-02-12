-- Menu Green - Development Row Level Security Policies
-- These policies are PERMISSIVE for development/testing purposes
-- WARNING: DO NOT USE IN PRODUCTION - Use schema_rls_prod.sql instead
-- Last updated: February 11, 2026

-- ============================================================
-- DEVELOPMENT MODE - All operations allowed for all tables
-- ============================================================

-- User Profiles - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on user_profiles" ON user_profiles;
CREATE POLICY "Dev: Allow all on user_profiles" ON user_profiles
  FOR ALL USING (true) WITH CHECK (true);

-- User Inventory - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on user_inventory" ON user_inventory;
CREATE POLICY "Dev: Allow all on user_inventory" ON user_inventory
  FOR ALL USING (true) WITH CHECK (true);

-- Daily Logs - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on daily_logs" ON daily_logs;
CREATE POLICY "Dev: Allow all on daily_logs" ON daily_logs
  FOR ALL USING (true) WITH CHECK (true);

-- Recipes - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on recipes" ON recipes;
CREATE POLICY "Dev: Allow all on recipes" ON recipes
  FOR ALL USING (true) WITH CHECK (true);

-- Recipe Ingredients - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on recipe_ingredients" ON recipe_ingredients;
CREATE POLICY "Dev: Allow all on recipe_ingredients" ON recipe_ingredients
  FOR ALL USING (true) WITH CHECK (true);

-- Ingredients - Allow all operations
DROP POLICY IF EXISTS "Dev: Allow all on ingredients" ON ingredients;
CREATE POLICY "Dev: Allow all on ingredients" ON ingredients
  FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- Enable RLS (but with permissive policies above)
-- ============================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Grant permissions
-- ============================================================

GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated, anon;

-- ============================================================
-- Development Notes:
-- ============================================================
-- This configuration allows:
-- - Anonymous access for testing without auth
-- - Full CRUD operations on all tables
-- - Easy data seeding and manipulation
-- 
-- Before deploying to production:
-- 1. Switch to schema_rls_prod.sql
-- 2. Set up proper authentication
-- 3. Test all user flows with restricted access
-- ============================================================
