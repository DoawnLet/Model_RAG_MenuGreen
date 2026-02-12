-- Menu Green - Production Row Level Security Policies
-- These policies enforce strict access control for production deployment
-- Last updated: February 11, 2026

-- ============================================================
-- User Profiles - Users can only access their own profile
-- ============================================================

DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile" ON user_profiles
  FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
CREATE POLICY "Users can insert own profile" ON user_profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- ============================================================
-- User Inventory - Users can only manage their own inventory
-- ============================================================

DROP POLICY IF EXISTS "Users can view own inventory" ON user_inventory;
CREATE POLICY "Users can view own inventory" ON user_inventory
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own inventory" ON user_inventory;
CREATE POLICY "Users can insert own inventory" ON user_inventory
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own inventory" ON user_inventory;
CREATE POLICY "Users can update own inventory" ON user_inventory
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own inventory" ON user_inventory;
CREATE POLICY "Users can delete own inventory" ON user_inventory
  FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- Daily Logs - Users can only access their own logs
-- ============================================================

DROP POLICY IF EXISTS "Users can view own logs" ON daily_logs;
CREATE POLICY "Users can view own logs" ON daily_logs
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own logs" ON daily_logs;
CREATE POLICY "Users can insert own logs" ON daily_logs
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own logs" ON daily_logs;
CREATE POLICY "Users can update own logs" ON daily_logs
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own logs" ON daily_logs;
CREATE POLICY "Users can delete own logs" ON daily_logs
  FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- Recipes - Public read access, admin-only write
-- ============================================================

DROP POLICY IF EXISTS "Recipes are viewable by everyone" ON recipes;
CREATE POLICY "Recipes are viewable by everyone" ON recipes
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Only admins can insert recipes" ON recipes;
CREATE POLICY "Only admins can insert recipes" ON recipes
  FOR INSERT WITH CHECK (
    (auth.jwt() ->> 'role')::text = 'admin' OR
    (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
  );

DROP POLICY IF EXISTS "Only admins can update recipes" ON recipes;
CREATE POLICY "Only admins can update recipes" ON recipes
  FOR UPDATE USING (
    (auth.jwt() ->> 'role')::text = 'admin' OR
    (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
  );

DROP POLICY IF EXISTS "Only admins can delete recipes" ON recipes;
CREATE POLICY "Only admins can delete recipes" ON recipes
  FOR DELETE USING (
    (auth.jwt() ->> 'role')::text = 'admin' OR
    (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
  );

-- ============================================================
-- Recipe Ingredients - Public read, admin write
-- ============================================================

DROP POLICY IF EXISTS "Recipe ingredients are viewable by everyone" ON recipe_ingredients;
CREATE POLICY "Recipe ingredients are viewable by everyone" ON recipe_ingredients
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Only admins can modify recipe ingredients" ON recipe_ingredients;
CREATE POLICY "Only admins can modify recipe ingredients" ON recipe_ingredients
  FOR ALL USING (
    (auth.jwt() ->> 'role')::text = 'admin' OR
    (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
  );

-- ============================================================
-- Ingredients - Public read, admin write
-- ============================================================

DROP POLICY IF EXISTS "Ingredients are viewable by everyone" ON ingredients;
CREATE POLICY "Ingredients are viewable by everyone" ON ingredients
  FOR SELECT USING (true);

DROP POLICY IF EXISTS "Only admins can modify ingredients" ON ingredients;
CREATE POLICY "Only admins can modify ingredients" ON ingredients
  FOR ALL USING (
    (auth.jwt() ->> 'role')::text = 'admin' OR
    (auth.jwt() -> 'user_metadata' ->> 'role')::text = 'admin'
  );

-- ============================================================
-- Enable RLS on all tables
-- ============================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Grant necessary permissions to authenticated users
-- ============================================================

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================================
-- Notes for deployment:
-- ============================================================
-- 1. Before applying: Back up your database
-- 2. Test with a non-admin user to verify access restrictions
-- 3. Ensure admin users have 'role' set to 'admin' in JWT claims or user_metadata
-- 4. Monitor Supabase logs for policy violations
-- 5. Consider adding rate limiting at the application level
-- ============================================================
