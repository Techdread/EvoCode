-- EvoCode Database Schema
-- SQLite database for storing LLM evaluation results

-- LLM Models configuration
CREATE TABLE IF NOT EXISTS llm_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    display_name TEXT NOT NULL,
    api_key TEXT,
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2048,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, model_name, endpoint)
);

-- Challenges (problems to solve)
CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    language TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    template TEXT,
    runner TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test cases for challenges
CREATE TABLE IF NOT EXISTS test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT NOT NULL,
    input TEXT NOT NULL,
    expected TEXT NOT NULL,
    is_hidden BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE
);

-- Evaluation runs (one LLM attempting one challenge)
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT NOT NULL,
    model_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'error')),
    best_fitness REAL DEFAULT 0.0,
    attempts_used INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 10,
    total_tokens_prompt INTEGER DEFAULT 0,
    total_tokens_completion INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id),
    FOREIGN KEY (model_id) REFERENCES llm_models(id)
);

-- Individual attempts within a run
CREATE TABLE IF NOT EXISTS evaluation_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    code TEXT NOT NULL,
    fitness REAL DEFAULT 0.0,
    tokens_prompt INTEGER DEFAULT 0,
    tokens_completion INTEGER DEFAULT 0,
    llm_latency_ms INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
);

-- Test results for each attempt
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    test_case_id INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    stdout TEXT,
    stderr TEXT,
    exit_code INTEGER,
    execution_time_ms INTEGER,
    memory_used_kb INTEGER,
    FOREIGN KEY (attempt_id) REFERENCES evaluation_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_challenge ON evaluation_runs(challenge_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_model ON evaluation_runs(model_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_status ON evaluation_runs(status);
CREATE INDEX IF NOT EXISTS idx_evaluation_attempts_run ON evaluation_attempts(run_id);
CREATE INDEX IF NOT EXISTS idx_test_results_attempt ON test_results(attempt_id);
CREATE INDEX IF NOT EXISTS idx_test_cases_challenge ON test_cases(challenge_id);

-- View: Model performance summary
CREATE VIEW IF NOT EXISTS v_model_performance AS
SELECT
    m.id AS model_id,
    m.display_name,
    m.provider,
    COUNT(DISTINCT r.id) AS total_runs,
    SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
    ROUND(100.0 * SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) / COUNT(DISTINCT r.id), 2) AS pass_rate,
    ROUND(AVG(r.best_fitness), 4) AS avg_fitness,
    ROUND(AVG(r.attempts_used), 2) AS avg_attempts,
    SUM(r.total_tokens_prompt) AS total_tokens_prompt,
    SUM(r.total_tokens_completion) AS total_tokens_completion
FROM llm_models m
LEFT JOIN evaluation_runs r ON m.id = r.model_id
GROUP BY m.id;

-- View: Challenge statistics
CREATE VIEW IF NOT EXISTS v_challenge_stats AS
SELECT
    c.id AS challenge_id,
    c.name,
    c.language,
    c.difficulty,
    COUNT(DISTINCT r.id) AS total_runs,
    SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
    ROUND(100.0 * SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT r.id), 0), 2) AS pass_rate,
    ROUND(AVG(CASE WHEN r.status = 'success' THEN r.attempts_used ELSE NULL END), 2) AS avg_attempts_to_solve,
    (SELECT COUNT(*) FROM test_cases tc WHERE tc.challenge_id = c.id AND NOT tc.is_hidden) AS visible_tests,
    (SELECT COUNT(*) FROM test_cases tc WHERE tc.challenge_id = c.id AND tc.is_hidden) AS hidden_tests
FROM challenges c
LEFT JOIN evaluation_runs r ON c.id = r.challenge_id
GROUP BY c.id;

-- View: Recent runs with details
CREATE VIEW IF NOT EXISTS v_recent_runs AS
SELECT
    r.id AS run_id,
    c.name AS challenge_name,
    c.language,
    c.difficulty,
    m.display_name AS model_name,
    r.status,
    r.best_fitness,
    r.attempts_used,
    r.max_attempts,
    r.total_tokens_prompt + r.total_tokens_completion AS total_tokens,
    r.started_at,
    r.completed_at,
    ROUND((julianday(r.completed_at) - julianday(r.started_at)) * 86400, 2) AS duration_seconds
FROM evaluation_runs r
JOIN challenges c ON r.challenge_id = c.id
JOIN llm_models m ON r.model_id = m.id
ORDER BY r.started_at DESC;
