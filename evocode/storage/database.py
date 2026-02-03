"""SQLite database connection manager for EvoCode."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator, Any

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "evocode.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """SQLite database connection manager with migration support."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database cursor with auto-commit."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL and return cursor."""
        conn = self.connect()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """Execute SQL with multiple parameter sets."""
        conn = self.connect()
        cursor = conn.executemany(sql, params_list)
        conn.commit()
        return cursor

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute SQL and fetch single row."""
        conn = self.connect()
        return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute SQL and fetch all rows."""
        conn = self.connect()
        return conn.execute(sql, params).fetchall()

    def init_schema(self):
        """Initialize database schema from migrations."""
        migration_file = MIGRATIONS_DIR / "001_initial.sql"
        if migration_file.exists():
            sql = migration_file.read_text()
            conn = self.connect()
            conn.executescript(sql)
            conn.commit()

    # LLM Models CRUD
    def add_model(
        self,
        provider: str,
        model_name: str,
        endpoint: str,
        display_name: str,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> int:
        """Add or update an LLM model configuration."""
        sql = """
            INSERT INTO llm_models (provider, model_name, endpoint, display_name, api_key, temperature, max_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, model_name, endpoint) DO UPDATE SET
                display_name = excluded.display_name,
                api_key = excluded.api_key,
                temperature = excluded.temperature,
                max_tokens = excluded.max_tokens
            RETURNING id
        """
        result = self.fetchone(sql, (provider, model_name, endpoint, display_name, api_key, temperature, max_tokens))
        return result["id"] if result else 0

    def get_models(self) -> list[dict]:
        """Get all configured LLM models."""
        rows = self.fetchall("SELECT * FROM llm_models ORDER BY display_name")
        return [dict(row) for row in rows]

    def get_model(self, model_id: int) -> Optional[dict]:
        """Get a specific LLM model by ID."""
        row = self.fetchone("SELECT * FROM llm_models WHERE id = ?", (model_id,))
        return dict(row) if row else None

    def delete_model(self, model_id: int):
        """Delete an LLM model."""
        self.execute("DELETE FROM llm_models WHERE id = ?", (model_id,))

    # Challenges CRUD
    def add_challenge(
        self,
        challenge_id: str,
        name: str,
        description: str,
        language: str,
        difficulty: str,
        runner: str,
        template: Optional[str] = None,
    ) -> str:
        """Add or update a challenge."""
        sql = """
            INSERT INTO challenges (id, name, description, language, difficulty, template, runner)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                language = excluded.language,
                difficulty = excluded.difficulty,
                template = excluded.template,
                runner = excluded.runner
        """
        self.execute(sql, (challenge_id, name, description, language, difficulty, template, runner))
        return challenge_id

    def add_test_case(
        self, challenge_id: str, input_data: str, expected: str, is_hidden: bool = False
    ) -> int:
        """Add a test case for a challenge."""
        sql = """
            INSERT INTO test_cases (challenge_id, input, expected, is_hidden)
            VALUES (?, ?, ?, ?)
        """
        cursor = self.execute(sql, (challenge_id, input_data, expected, is_hidden))
        return cursor.lastrowid or 0

    def get_challenges(self) -> list[dict]:
        """Get all challenges."""
        rows = self.fetchall("SELECT * FROM challenges ORDER BY name")
        return [dict(row) for row in rows]

    def get_challenge(self, challenge_id: str) -> Optional[dict]:
        """Get a specific challenge by ID."""
        row = self.fetchone("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
        return dict(row) if row else None

    def get_test_cases(self, challenge_id: str, include_hidden: bool = True) -> list[dict]:
        """Get test cases for a challenge."""
        if include_hidden:
            rows = self.fetchall(
                "SELECT * FROM test_cases WHERE challenge_id = ? ORDER BY id",
                (challenge_id,),
            )
        else:
            rows = self.fetchall(
                "SELECT * FROM test_cases WHERE challenge_id = ? AND is_hidden = FALSE ORDER BY id",
                (challenge_id,),
            )
        return [dict(row) for row in rows]

    def clear_test_cases(self, challenge_id: str):
        """Remove all test cases for a challenge (and their test results)."""
        # First delete test_results that reference these test_cases
        self.execute("""
            DELETE FROM test_results
            WHERE test_case_id IN (SELECT id FROM test_cases WHERE challenge_id = ?)
        """, (challenge_id,))
        # Then delete the test_cases
        self.execute("DELETE FROM test_cases WHERE challenge_id = ?", (challenge_id,))

    def delete_challenge(self, challenge_id: str):
        """Delete a challenge and its test cases."""
        self.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))

    # Evaluation Runs CRUD
    def create_run(
        self, challenge_id: str, model_id: int, max_attempts: int = 10
    ) -> int:
        """Create a new evaluation run."""
        sql = """
            INSERT INTO evaluation_runs (challenge_id, model_id, status, max_attempts)
            VALUES (?, ?, 'running', ?)
        """
        cursor = self.execute(sql, (challenge_id, model_id, max_attempts))
        return cursor.lastrowid or 0

    def update_run(
        self,
        run_id: int,
        status: Optional[str] = None,
        best_fitness: Optional[float] = None,
        attempts_used: Optional[int] = None,
        total_tokens_prompt: Optional[int] = None,
        total_tokens_completion: Optional[int] = None,
        completed: bool = False,
    ):
        """Update an evaluation run."""
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if best_fitness is not None:
            updates.append("best_fitness = ?")
            params.append(best_fitness)
        if attempts_used is not None:
            updates.append("attempts_used = ?")
            params.append(attempts_used)
        if total_tokens_prompt is not None:
            updates.append("total_tokens_prompt = ?")
            params.append(total_tokens_prompt)
        if total_tokens_completion is not None:
            updates.append("total_tokens_completion = ?")
            params.append(total_tokens_completion)
        if completed:
            updates.append("completed_at = CURRENT_TIMESTAMP")

        if updates:
            sql = f"UPDATE evaluation_runs SET {', '.join(updates)} WHERE id = ?"
            params.append(run_id)
            self.execute(sql, tuple(params))

    def get_run(self, run_id: int) -> Optional[dict]:
        """Get an evaluation run by ID."""
        row = self.fetchone("SELECT * FROM evaluation_runs WHERE id = ?", (run_id,))
        return dict(row) if row else None

    def get_runs(
        self,
        challenge_id: Optional[str] = None,
        model_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get evaluation runs with optional filters."""
        conditions = []
        params = []

        if challenge_id:
            conditions.append("challenge_id = ?")
            params.append(challenge_id)
        if model_id:
            conditions.append("model_id = ?")
            params.append(model_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM evaluation_runs {where_clause} ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        rows = self.fetchall(sql, tuple(params))
        return [dict(row) for row in rows]

    # Evaluation Attempts CRUD
    def create_attempt(
        self,
        run_id: int,
        attempt_number: int,
        code: str,
        fitness: float = 0.0,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        llm_latency_ms: int = 0,
        execution_time_ms: int = 0,
        feedback: Optional[str] = None,
    ) -> int:
        """Create a new evaluation attempt."""
        sql = """
            INSERT INTO evaluation_attempts
            (run_id, attempt_number, code, fitness, tokens_prompt, tokens_completion, llm_latency_ms, execution_time_ms, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute(
            sql,
            (run_id, attempt_number, code, fitness, tokens_prompt, tokens_completion, llm_latency_ms, execution_time_ms, feedback),
        )
        return cursor.lastrowid or 0

    def get_attempts(self, run_id: int) -> list[dict]:
        """Get all attempts for a run."""
        rows = self.fetchall(
            "SELECT * FROM evaluation_attempts WHERE run_id = ? ORDER BY attempt_number",
            (run_id,),
        )
        return [dict(row) for row in rows]

    def get_attempt(self, attempt_id: int) -> Optional[dict]:
        """Get a specific attempt by ID."""
        row = self.fetchone("SELECT * FROM evaluation_attempts WHERE id = ?", (attempt_id,))
        return dict(row) if row else None

    # Test Results CRUD
    def add_test_result(
        self,
        attempt_id: int,
        test_case_id: int,
        passed: bool,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        exit_code: Optional[int] = None,
        execution_time_ms: Optional[int] = None,
        memory_used_kb: Optional[int] = None,
    ) -> int:
        """Add a test result for an attempt."""
        sql = """
            INSERT INTO test_results
            (attempt_id, test_case_id, passed, stdout, stderr, exit_code, execution_time_ms, memory_used_kb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute(
            sql,
            (attempt_id, test_case_id, passed, stdout, stderr, exit_code, execution_time_ms, memory_used_kb),
        )
        return cursor.lastrowid or 0

    def get_test_results(self, attempt_id: int) -> list[dict]:
        """Get all test results for an attempt."""
        rows = self.fetchall(
            "SELECT * FROM test_results WHERE attempt_id = ? ORDER BY test_case_id",
            (attempt_id,),
        )
        return [dict(row) for row in rows]

    # Views/Statistics
    def get_model_performance(self) -> list[dict]:
        """Get model performance statistics."""
        rows = self.fetchall("SELECT * FROM v_model_performance")
        return [dict(row) for row in rows]

    def get_challenge_stats(self) -> list[dict]:
        """Get challenge statistics."""
        rows = self.fetchall("SELECT * FROM v_challenge_stats")
        return [dict(row) for row in rows]

    def get_recent_runs(self, limit: int = 50) -> list[dict]:
        """Get recent evaluation runs with details."""
        rows = self.fetchall(f"SELECT * FROM v_recent_runs LIMIT ?", (limit,))
        return [dict(row) for row in rows]


# Singleton database instance
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """Get or create the singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
        _db_instance.init_schema()
    return _db_instance
