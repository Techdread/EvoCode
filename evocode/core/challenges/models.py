"""Data models for challenges."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestCase:
    """A single test case for a challenge."""
    input: str
    expected: str
    is_hidden: bool = False
    id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "input": self.input,
            "expected": self.expected,
            "is_hidden": self.is_hidden,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        """Create from dictionary."""
        return cls(
            input=data.get("input", ""),
            expected=data.get("expected", ""),
            is_hidden=data.get("is_hidden", False),
            id=data.get("id"),
        )


@dataclass
class Challenge:
    """A coding challenge with test cases."""
    id: str
    name: str
    description: str
    language: str
    difficulty: str  # easy, medium, hard
    runner: str  # Code template with {{solution}} placeholder
    template: Optional[str] = None  # Starting code template
    test_cases: list[TestCase] = field(default_factory=list)
    hidden_tests: list[TestCase] = field(default_factory=list)

    def __post_init__(self):
        # Mark hidden tests
        for tc in self.hidden_tests:
            tc.is_hidden = True

    @property
    def all_test_cases(self) -> list[TestCase]:
        """Get all test cases (visible and hidden)."""
        return self.test_cases + self.hidden_tests

    @property
    def visible_test_cases(self) -> list[TestCase]:
        """Get only visible test cases."""
        return [tc for tc in self.test_cases if not tc.is_hidden]

    def build_code(self, solution: str) -> str:
        """
        Build executable code by inserting solution into runner template.

        Args:
            solution: The solution code to insert

        Returns:
            Complete runnable code
        """
        return self.runner.replace("{{solution}}", solution)

    def to_dict(self) -> dict:
        """Convert to dictionary (for YAML serialization)."""
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "difficulty": self.difficulty,
            "runner": self.runner,
        }
        if self.template:
            data["template"] = self.template

        if self.test_cases:
            data["test_cases"] = [
                {"input": tc.input, "expected": tc.expected}
                for tc in self.test_cases
            ]

        if self.hidden_tests:
            data["hidden_tests"] = [
                {"input": tc.input, "expected": tc.expected}
                for tc in self.hidden_tests
            ]

        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Challenge":
        """Create from dictionary (from YAML)."""
        test_cases = [
            TestCase(
                input=tc.get("input", ""),
                expected=tc.get("expected", ""),
                is_hidden=False,
            )
            for tc in data.get("test_cases", [])
        ]

        hidden_tests = [
            TestCase(
                input=tc.get("input", ""),
                expected=tc.get("expected", ""),
                is_hidden=True,
            )
            for tc in data.get("hidden_tests", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            language=data["language"],
            difficulty=data.get("difficulty", "medium"),
            runner=data["runner"],
            template=data.get("template"),
            test_cases=test_cases,
            hidden_tests=hidden_tests,
        )

    def get_prompt(self, include_visible_tests: bool = True) -> str:
        """
        Generate a prompt for the LLM to solve this challenge.

        Args:
            include_visible_tests: Whether to include visible test cases in prompt

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"# {self.name}",
            "",
            self.description,
            "",
        ]

        if self.template:
            prompt_parts.extend([
                "## Starting Template",
                f"```{self.language}",
                self.template,
                "```",
                "",
            ])

        if include_visible_tests and self.test_cases:
            prompt_parts.append("## Examples")
            for i, tc in enumerate(self.test_cases[:3], 1):  # Show up to 3 examples
                prompt_parts.extend([
                    f"### Example {i}",
                    f"Input: {tc.input}",
                    f"Output: {tc.expected}",
                    "",
                ])

        prompt_parts.extend([
            "## Requirements",
            f"- Write your solution in {self.language}",
            "- Output ONLY the code, no explanations",
            "- The code will be tested against additional hidden test cases",
        ])

        return "\n".join(prompt_parts)

    def get_feedback_prompt(
        self,
        previous_code: str,
        test_results: list[dict],
        attempt_number: int,
    ) -> str:
        """
        Generate a feedback prompt after a failed attempt.

        Args:
            previous_code: The code from the previous attempt
            test_results: List of test results with pass/fail info
            attempt_number: Current attempt number

        Returns:
            Formatted feedback prompt
        """
        failed_tests = [r for r in test_results if not r.get("passed", False)]

        prompt_parts = [
            f"# Attempt {attempt_number} Failed",
            "",
            "Your previous solution did not pass all test cases.",
            "",
            "## Your Previous Code",
            f"```{self.language}",
            previous_code,
            "```",
            "",
            f"## Failed Tests ({len(failed_tests)}/{len(test_results)})",
        ]

        for i, result in enumerate(failed_tests[:5], 1):  # Show up to 5 failures
            prompt_parts.extend([
                f"### Test {i}",
                f"Input: {result.get('input', 'N/A')}",
                f"Expected: {result.get('expected', 'N/A')}",
                f"Got: {result.get('actual', 'N/A')}",
            ])

            # Include error info if available
            stderr = result.get("stderr", "")
            if stderr:
                prompt_parts.append(f"Error: {stderr[:500]}")

            prompt_parts.append("")

        prompt_parts.extend([
            "## Instructions",
            "Please fix your code to handle these cases correctly.",
            "Output ONLY the corrected code, no explanations.",
        ])

        return "\n".join(prompt_parts)
