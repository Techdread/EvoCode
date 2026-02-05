"""Main evaluation loop for running LLM code generation."""

from dataclasses import dataclass, field
from typing import Optional, Callable
import time

from core.llm import BaseLLMProvider, LLMResponse
from core.judge import Judge0Client, TestCaseResult
from core.challenges import Challenge, TestCase
from storage import Database


@dataclass
class AttemptResult:
    """Result of a single evaluation attempt."""
    attempt_number: int
    code: str
    fitness: float
    test_results: list[TestCaseResult]
    llm_response: LLMResponse
    execution_time_ms: int = 0
    passed: bool = False


@dataclass
class EvaluationResult:
    """Final result of an evaluation run."""
    run_id: int
    challenge_id: str
    model_id: int
    status: str  # success, failed, error
    best_fitness: float
    attempts_used: int
    total_tokens_prompt: int
    total_tokens_completion: int
    attempts: list[AttemptResult] = field(default_factory=list)
    final_code: Optional[str] = None
    error_message: Optional[str] = None


class EvaluationRunner:
    """
    Main evaluation loop for testing LLM code generation.

    The evaluation flow:
    1. Build initial prompt with problem description
    2. LLM generates code
    3. Judge0 runs code against all test cases
    4. If all pass → success
    5. If failures → build feedback prompt with errors, loop to step 2
    6. Stop after max_attempts
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        judge: Judge0Client,
        db: Optional[Database] = None,
        max_attempts: int = 10,
    ):
        self.llm = llm
        self.judge = judge
        self.db = db
        self.max_attempts = max_attempts

    def run(
        self,
        challenge: Challenge,
        model_id: int,
        progress_callback: Optional[Callable[[int, float, str], None]] = None,
        run_id: Optional[int] = None,
    ) -> EvaluationResult:
        """
        Run evaluation for a challenge.

        Args:
            challenge: The challenge to solve
            model_id: Database ID of the LLM model
            progress_callback: Optional callback(attempt_number, fitness, status)
            run_id: Optional existing run_id (for batch runs)

        Returns:
            EvaluationResult with final status and all attempts
        """
        # Create run record in database (if not provided)
        if run_id is None:
            run_id = 0
            if self.db:
                run_id = self.db.create_run(
                    challenge_id=challenge.id,
                    model_id=model_id,
                    max_attempts=self.max_attempts,
                )

        result = EvaluationResult(
            run_id=run_id,
            challenge_id=challenge.id,
            model_id=model_id,
            status="running",
            best_fitness=0.0,
            attempts_used=0,
            total_tokens_prompt=0,
            total_tokens_completion=0,
        )

        try:
            # Get all test cases
            test_cases = challenge.all_test_cases
            test_case_dicts = [
                {"id": i, "input": tc.input, "expected": tc.expected}
                for i, tc in enumerate(test_cases)
            ]

            previous_code = None
            previous_results = None

            for attempt_num in range(1, self.max_attempts + 1):
                if progress_callback:
                    progress_callback(attempt_num, result.best_fitness, "generating")

                # Generate code
                attempt_result = self._run_attempt(
                    challenge=challenge,
                    test_case_dicts=test_case_dicts,
                    attempt_number=attempt_num,
                    previous_code=previous_code,
                    previous_results=previous_results,
                )

                # Update totals
                result.attempts.append(attempt_result)
                result.attempts_used = attempt_num
                result.total_tokens_prompt += attempt_result.llm_response.tokens_prompt
                result.total_tokens_completion += attempt_result.llm_response.tokens_completion

                if attempt_result.fitness > result.best_fitness:
                    result.best_fitness = attempt_result.fitness
                    result.final_code = attempt_result.code

                # Save attempt to database
                if self.db:
                    attempt_id = self._save_attempt(run_id, challenge.id, attempt_result, test_cases)

                if progress_callback:
                    progress_callback(attempt_num, attempt_result.fitness, "tested")

                # Check if solved
                if attempt_result.passed:
                    result.status = "success"
                    break

                # Prepare for next iteration
                previous_code = attempt_result.code
                previous_results = [
                    {
                        "input": tr.input,
                        "expected": tr.expected,
                        "actual": tr.actual,
                        "passed": tr.passed,
                        "stderr": tr.execution.stderr,
                    }
                    for tr in attempt_result.test_results
                ]

            # Finalize status
            if result.status != "success":
                result.status = "failed"

        except Exception as e:
            result.status = "error"
            result.error_message = str(e)

        # Update run record
        if self.db:
            self.db.update_run(
                run_id=run_id,
                status=result.status,
                best_fitness=result.best_fitness,
                attempts_used=result.attempts_used,
                total_tokens_prompt=result.total_tokens_prompt,
                total_tokens_completion=result.total_tokens_completion,
                completed=True,
            )

        return result

    def _run_attempt(
        self,
        challenge: Challenge,
        test_case_dicts: list[dict],
        attempt_number: int,
        previous_code: Optional[str],
        previous_results: Optional[list[dict]],
    ) -> AttemptResult:
        """Run a single generation and test attempt."""

        # Build prompt
        if previous_code and previous_results:
            prompt = challenge.get_feedback_prompt(
                previous_code=previous_code,
                test_results=previous_results,
                attempt_number=attempt_number,
            )
        else:
            prompt = challenge.get_prompt(include_visible_tests=True)

        # Generate code
        start_time = time.time()

        # Check if using server defaults (LM Studio Direct Mode)
        use_server_defaults = getattr(self.llm, '_use_server_defaults', False)

        if use_server_defaults:
            # Let LM Studio use its own settings
            llm_response = self.llm.generate(
                prompt=prompt,
                system_prompt=self._get_system_prompt(challenge.language),
                use_server_defaults=True,
            )
        else:
            llm_response = self.llm.generate(
                prompt=prompt,
                system_prompt=self._get_system_prompt(challenge.language),
                temperature=0.3 if attempt_number == 1 else 0.5,  # Slightly higher temp for retries
            )

        # Extract code from response
        code = self.llm._extract_code(llm_response.content, challenge.language)

        # Build executable code
        executable = challenge.build_code(code)

        # Run tests
        test_start = time.time()
        test_results, fitness = self.judge.run_test_cases(
            source_code=executable,
            language=challenge.language,
            test_cases=test_case_dicts,
        )
        execution_time_ms = int((time.time() - test_start) * 1000)

        passed = fitness == 1.0

        return AttemptResult(
            attempt_number=attempt_number,
            code=code,
            fitness=fitness,
            test_results=test_results,
            llm_response=llm_response,
            execution_time_ms=execution_time_ms,
            passed=passed,
        )

    def _get_system_prompt(self, language: str) -> str:
        """Get system prompt for code generation."""
        return f"""You are an expert {language} programmer solving coding challenges.

Rules:
1. Output ONLY the solution code - no explanations, no markdown, no code blocks
2. The code must be complete and correct
3. Handle all edge cases
4. If you see a function template, implement that function
5. Do not include test code or main() unless specifically required"""

    def _save_attempt(
        self,
        run_id: int,
        challenge_id: str,
        attempt: AttemptResult,
        test_cases: list[TestCase],
    ) -> int:
        """Save attempt and test results to database."""
        if not self.db:
            return 0

        # Build feedback string
        failed = [tr for tr in attempt.test_results if not tr.passed]
        feedback = None
        if failed:
            feedback = f"{len(failed)} tests failed. "
            first_fail = failed[0]
            feedback += f"First failure: expected '{first_fail.expected}', got '{first_fail.actual}'"

        # Create attempt record
        attempt_id = self.db.create_attempt(
            run_id=run_id,
            attempt_number=attempt.attempt_number,
            code=attempt.code,
            fitness=attempt.fitness,
            tokens_prompt=attempt.llm_response.tokens_prompt,
            tokens_completion=attempt.llm_response.tokens_completion,
            llm_latency_ms=attempt.llm_response.latency_ms,
            execution_time_ms=attempt.execution_time_ms,
            feedback=feedback,
        )

        # Save test results
        # Get test cases from database by challenge_id
        db_test_cases = self.db.get_test_cases(challenge_id)

        for tr in attempt.test_results:
            # Find matching test case ID by input/expected
            tc_id = None
            for db_tc in db_test_cases:
                if db_tc["input"] == tr.input and db_tc["expected"] == tr.expected:
                    tc_id = db_tc["id"]
                    break

            # Only save if we found a matching test case in DB
            if tc_id is not None:
                self.db.add_test_result(
                    attempt_id=attempt_id,
                    test_case_id=tc_id,
                    passed=tr.passed,
                    stdout=tr.actual,
                    stderr=tr.execution.stderr,
                    exit_code=tr.execution.exit_code,
                    execution_time_ms=tr.execution.time_ms,
                    memory_used_kb=tr.execution.memory_kb,
                )

        return attempt_id


def run_evaluation(
    challenge: Challenge,
    llm: BaseLLMProvider,
    judge: Judge0Client,
    model_id: int,
    db: Optional[Database] = None,
    max_attempts: int = 10,
    progress_callback: Optional[Callable[[int, float, str], None]] = None,
    run_id: Optional[int] = None,
) -> EvaluationResult:
    """
    Convenience function to run an evaluation.

    Args:
        challenge: Challenge to solve
        llm: LLM provider instance
        judge: Judge0 client instance
        model_id: Database ID of the model
        db: Optional database instance
        max_attempts: Maximum attempts allowed
        progress_callback: Optional progress callback
        run_id: Optional existing run_id (for batch runs)

    Returns:
        EvaluationResult
    """
    runner = EvaluationRunner(
        llm=llm,
        judge=judge,
        db=db,
        max_attempts=max_attempts,
    )
    return runner.run(challenge, model_id, progress_callback, run_id)
