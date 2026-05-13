-- Supabase RPC function for pgvector similarity search
-- Run this in Supabase SQL Editor after creating the schema

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
