-- Table for LangGraph Checkpoints
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

-- Table for LangGraph Checkpoint Writes
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

-- Enable RLS (Optional but recommended)
ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoint_writes ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all operations for authenticated users (service role will bypass)
-- Adjust this based on your security model. 
-- For now, we allow public access for simplicity in MVP/Dev, 
-- but in production, you should restrict this to the service role or specific users.
CREATE POLICY "Allow all access to checkpoints" ON checkpoints FOR ALL USING (true);
CREATE POLICY "Allow all access to checkpoint_writes" ON checkpoint_writes FOR ALL USING (true);
