-- Batch Runs Schema
-- Groups multiple evaluation runs together for batch evaluation

-- Batch runs table
CREATE TABLE IF NOT EXISTS batch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'cancelled')) DEFAULT 'running',
    total_runs INTEGER DEFAULT 0,
    completed_runs INTEGER DEFAULT 0,
    successful_runs INTEGER DEFAULT 0,
    failed_runs INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Add batch_id column to evaluation_runs (nullable for backwards compatibility)
ALTER TABLE evaluation_runs ADD COLUMN batch_id INTEGER REFERENCES batch_runs(id);

-- Index for batch lookups
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_batch ON evaluation_runs(batch_id);

-- View: Batch run summary
CREATE VIEW IF NOT EXISTS v_batch_runs AS
SELECT
    b.id AS batch_id,
    b.name,
    b.status,
    b.total_runs,
    b.completed_runs,
    b.successful_runs,
    b.failed_runs,
    ROUND(100.0 * b.successful_runs / NULLIF(b.completed_runs, 0), 2) AS pass_rate,
    b.created_at,
    b.completed_at,
    ROUND((julianday(b.completed_at) - julianday(b.created_at)) * 86400, 2) AS duration_seconds,
    m.display_name AS model_name
FROM batch_runs b
LEFT JOIN evaluation_runs r ON b.id = r.batch_id
LEFT JOIN llm_models m ON r.model_id = m.id
GROUP BY b.id
ORDER BY b.created_at DESC;
