-- Add model_id to batch_runs table
ALTER TABLE batch_runs ADD COLUMN model_id INTEGER REFERENCES llm_models(id);

-- Index for model lookups
CREATE INDEX IF NOT EXISTS idx_batch_runs_model ON batch_runs(model_id);
