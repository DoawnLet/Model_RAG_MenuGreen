-- Supabase RPC function for pgvector similarity search
-- Run this in Supabase SQL Editor after creating the schema

DROP FUNCTION IF EXISTS match_recipes;

CREATE OR REPLACE FUNCTION match_recipes(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    description TEXT,
    prep_time_minutes INT,
    cook_time_minutes INT,
    servings INT,
    similarity FLOAT
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
        1 - (r.embedding <=> query_embedding) AS similarity
    FROM recipes r
    WHERE r.embedding IS NOT NULL
        AND 1 - (r.embedding <=> query_embedding) > match_threshold
    ORDER BY r.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
