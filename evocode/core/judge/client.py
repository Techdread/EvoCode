"""Judge0 API client for code execution."""

import base64
import time
from dataclasses import dataclass
from typing import Optional
import requests

from .languages import get_language_id


@dataclass
class ExecutionResult:
    """Result of code execution."""
    stdout: str
    stderr: str
    exit_code: int
    status: str  # e.g., "Accepted", "Wrong Answer", "Time Limit Exceeded"
    status_id: int
    time_ms: int
    memory_kb: int
    compile_output: Optional[str] = None
    message: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if execution completed successfully (status_id == 3)."""
        return self.status_id == 3


@dataclass
class TestCaseResult:
    """Result of running a test case."""
    test_case_id: int
    input: str
    expected: str
    actual: str
    passed: bool
    execution: ExecutionResult


class Judge0Client:
    """Client for interacting with Judge0 API."""

    # Status IDs from Judge0
    STATUS_IN_QUEUE = 1
    STATUS_PROCESSING = 2
    STATUS_ACCEPTED = 3
    STATUS_WRONG_ANSWER = 4
    STATUS_TIME_LIMIT = 5
    STATUS_COMPILATION_ERROR = 6
    STATUS_RUNTIME_ERROR_SIGSEGV = 7
    STATUS_RUNTIME_ERROR_SIGXFSZ = 8
    STATUS_RUNTIME_ERROR_SIGFPE = 9
    STATUS_RUNTIME_ERROR_SIGABRT = 10
    STATUS_RUNTIME_ERROR_NZEC = 11
    STATUS_RUNTIME_ERROR_OTHER = 12
    STATUS_INTERNAL_ERROR = 13
    STATUS_EXEC_FORMAT_ERROR = 14

    def __init__(
        self,
        base_url: str = "http://localhost:2358",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-Auth-Token"] = api_key

    def health_check(self) -> bool:
        """Check if Judge0 is available."""
        try:
            response = self.session.get(
                f"{self.base_url}/about",
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_languages(self) -> list[dict]:
        """Get list of available languages from Judge0."""
        response = self.session.get(
            f"{self.base_url}/languages",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def submit(
        self,
        source_code: str,
        language: str | int,
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: float = 5.0,
        wall_time_limit: float = 15.0,
        memory_limit: int = 128000,  # KB
        wait: bool = True,
    ) -> ExecutionResult:
        """
        Submit code for execution.

        Args:
            source_code: The code to execute
            language: Language name or Judge0 language ID
            stdin: Input to provide via stdin
            expected_output: Expected output for comparison
            cpu_time_limit: CPU time limit in seconds
            wall_time_limit: Wall clock time limit in seconds
            memory_limit: Memory limit in KB
            wait: If True, wait for result synchronously

        Returns:
            ExecutionResult with the execution details
        """
        # Get language ID if string provided
        language_id = language if isinstance(language, int) else get_language_id(language)

        # Build payload
        payload = {
            "source_code": base64.b64encode(source_code.encode()).decode(),
            "language_id": language_id,
            "stdin": base64.b64encode(stdin.encode()).decode() if stdin else "",
            "cpu_time_limit": cpu_time_limit,
            "wall_time_limit": wall_time_limit,
            "memory_limit": memory_limit,
        }

        if expected_output is not None:
            payload["expected_output"] = base64.b64encode(expected_output.encode()).decode()

        # Submit with wait parameter
        params = {"base64_encoded": "true", "wait": str(wait).lower()}

        response = self.session.post(
            f"{self.base_url}/submissions",
            json=payload,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()

        if wait:
            return self._parse_result(result)

        # Return a placeholder if not waiting
        return ExecutionResult(
            stdout="",
            stderr="",
            exit_code=-1,
            status="Pending",
            status_id=self.STATUS_IN_QUEUE,
            time_ms=0,
            memory_kb=0,
        )

    def get_submission(self, token: str) -> ExecutionResult:
        """Get the result of a submission by token."""
        params = {"base64_encoded": "true"}
        response = self.session.get(
            f"{self.base_url}/submissions/{token}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._parse_result(response.json())

    def _parse_result(self, data: dict) -> ExecutionResult:
        """Parse Judge0 response into ExecutionResult."""
        def decode(s: Optional[str]) -> str:
            if s is None:
                return ""
            try:
                return base64.b64decode(s).decode("utf-8", errors="replace")
            except Exception:
                return s

        stdout = decode(data.get("stdout"))
        stderr = decode(data.get("stderr"))
        compile_output = decode(data.get("compile_output")) if data.get("compile_output") else None
        message = data.get("message")

        # Parse time (comes as string like "0.001" in seconds)
        time_str = data.get("time", "0")
        try:
            time_ms = int(float(time_str) * 1000)
        except (ValueError, TypeError):
            time_ms = 0

        # Parse memory
        memory_kb = data.get("memory", 0) or 0

        # Get status
        status_data = data.get("status", {})
        status_id = status_data.get("id", 0)
        status_desc = status_data.get("description", "Unknown")

        # Determine exit code
        exit_code = data.get("exit_code", 0) or 0
        if status_id != self.STATUS_ACCEPTED:
            exit_code = exit_code or 1

        return ExecutionResult(
            stdout=stdout.rstrip("\n"),
            stderr=stderr,
            exit_code=exit_code,
            status=status_desc,
            status_id=status_id,
            time_ms=time_ms,
            memory_kb=memory_kb,
            compile_output=compile_output,
            message=message,
        )

    def run_test_case(
        self,
        source_code: str,
        language: str | int,
        test_input: str,
        expected_output: str,
        test_case_id: int = 0,
    ) -> TestCaseResult:
        """
        Run code against a single test case.

        Args:
            source_code: The code to execute
            language: Language name or Judge0 language ID
            test_input: Input to provide via stdin
            expected_output: Expected output
            test_case_id: ID of the test case for tracking

        Returns:
            TestCaseResult with pass/fail status and details
        """
        result = self.submit(
            source_code=source_code,
            language=language,
            stdin=test_input,
            expected_output=expected_output,
            wait=True,
        )

        # Compare output (normalize whitespace)
        actual = result.stdout.strip()
        expected = expected_output.strip()
        passed = actual == expected and result.status_id == self.STATUS_ACCEPTED

        return TestCaseResult(
            test_case_id=test_case_id,
            input=test_input,
            expected=expected,
            actual=actual,
            passed=passed,
            execution=result,
        )

    def run_test_cases(
        self,
        source_code: str,
        language: str | int,
        test_cases: list[dict],
    ) -> tuple[list[TestCaseResult], float]:
        """
        Run code against multiple test cases.

        Args:
            source_code: The code to execute
            language: Language name or Judge0 language ID
            test_cases: List of dicts with 'id', 'input', 'expected' keys

        Returns:
            Tuple of (list of TestCaseResult, fitness score 0-1)
        """
        results = []
        passed_count = 0

        for tc in test_cases:
            result = self.run_test_case(
                source_code=source_code,
                language=language,
                test_input=tc.get("input", ""),
                expected_output=tc.get("expected", ""),
                test_case_id=tc.get("id", 0),
            )
            results.append(result)
            if result.passed:
                passed_count += 1

        fitness = passed_count / len(test_cases) if test_cases else 0.0
        return results, fitness
