-- Enable Row Level Security
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;

-- Policy to allow anyone to READ recipes
CREATE POLICY "Enable read access for all users" ON recipes
    FOR SELECT USING (true);

-- Policy to allow authenticated/anon users to INSERT recipes (for development)
-- In production, restrict this to service_role or specific admin users
CREATE POLICY "Enable insert for authenticated users only" ON recipes
    FOR INSERT WITH CHECK (true);

-- Policy to allow update
CREATE POLICY "Enable update for all users" ON recipes
    FOR UPDATE USING (true);
    
-- Policy to allow delete
CREATE POLICY "Enable delete for all users" ON recipes
    FOR DELETE USING (true);
