"""LLM-powered test case generator for challenges."""

import json
import re
from typing import Optional

from ..llm import BaseLLMProvider
from .models import Challenge, TestCase


class TestCaseGenerator:
    """Generate additional test cases using an LLM."""

    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm

    def generate_test_cases(
        self,
        challenge: Challenge,
        num_cases: int = 5,
        focus: str = "edge_cases",
    ) -> list[TestCase]:
        """
        Generate additional test cases for a challenge.

        Args:
            challenge: The challenge to generate tests for
            num_cases: Number of test cases to generate
            focus: Type of cases to focus on ("edge_cases", "random", "stress")

        Returns:
            List of generated TestCase objects
        """
        system_prompt = """You are an expert test case generator. Generate test cases that thoroughly test code correctness.

Your output must be valid JSON only - no explanations, no markdown formatting.

Output format:
[
  {"input": "...", "expected": "..."},
  {"input": "...", "expected": "..."}
]"""

        focus_guidance = {
            "edge_cases": "Focus on edge cases: empty inputs, single elements, boundary values, special characters, minimum/maximum values.",
            "random": "Generate diverse random test cases covering typical usage scenarios.",
            "stress": "Generate stress test cases with larger inputs to test performance.",
        }

        prompt = f"""Generate {num_cases} test cases for this challenge:

## Challenge: {challenge.name}

{challenge.description}

## Existing Test Cases
{self._format_existing_tests(challenge)}

## Focus
{focus_guidance.get(focus, focus_guidance["edge_cases"])}

## Requirements
- Generate exactly {num_cases} NEW test cases (don't repeat existing ones)
- Each test case must have correct expected output
- Consider the input/output format of existing tests
- Output valid JSON array only"""

        response = self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return self._parse_test_cases(response.content)

    def _format_existing_tests(self, challenge: Challenge) -> str:
        """Format existing test cases for the prompt."""
        tests = challenge.test_cases[:5]  # Show up to 5 examples
        lines = []
        for tc in tests:
            lines.append(f"Input: {tc.input}")
            lines.append(f"Expected: {tc.expected}")
            lines.append("")
        return "\n".join(lines)

    def _parse_test_cases(self, content: str) -> list[TestCase]:
        """Parse LLM response into TestCase objects."""
        # Try to extract JSON from response
        content = content.strip()

        # Try to find JSON array in response
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            content = json_match.group()

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [
                    TestCase(
                        input=str(tc.get("input", "")),
                        expected=str(tc.get("expected", "")),
                        is_hidden=True,
                    )
                    for tc in data
                    if "input" in tc and "expected" in tc
                ]
        except json.JSONDecodeError:
            pass

        return []

    def augment_challenge(
        self,
        challenge: Challenge,
        num_edge_cases: int = 3,
        num_random: int = 2,
    ) -> Challenge:
        """
        Augment a challenge with additional LLM-generated test cases.

        Args:
            challenge: The challenge to augment
            num_edge_cases: Number of edge case tests to add
            num_random: Number of random tests to add

        Returns:
            Challenge with additional hidden tests
        """
        new_tests = []

        if num_edge_cases > 0:
            edge_tests = self.generate_test_cases(
                challenge,
                num_cases=num_edge_cases,
                focus="edge_cases",
            )
            new_tests.extend(edge_tests)

        if num_random > 0:
            random_tests = self.generate_test_cases(
                challenge,
                num_cases=num_random,
                focus="random",
            )
            new_tests.extend(random_tests)

        # Add to challenge's hidden tests
        challenge.hidden_tests.extend(new_tests)

        return challenge


def generate_challenge_from_description(
    llm: BaseLLMProvider,
    description: str,
    language: str = "python",
    difficulty: str = "medium",
) -> Optional[Challenge]:
    """
    Generate a complete challenge from a problem description.

    Args:
        llm: LLM provider for generation
        description: Problem description/idea
        language: Target programming language
        difficulty: Challenge difficulty level

    Returns:
        Generated Challenge object or None if generation fails
    """
    system_prompt = """You are an expert coding challenge designer. Create well-defined programming challenges with clear requirements and test cases.

Output valid YAML only - no explanations or markdown code fences."""

    prompt = f"""Create a coding challenge based on this idea:

{description}

Requirements:
- Language: {language}
- Difficulty: {difficulty}
- Include 3-5 visible test cases (examples)
- Include 5-8 hidden test cases (for thorough testing)
- Clear function signature in template
- Runner that handles stdin/stdout

Output as YAML with this structure:
id: snake_case_id
name: "Challenge Name"
language: {language}
difficulty: {difficulty}
description: |
  Clear problem description...
template: |
  def solve(...):
      pass
runner: |
  {{{{solution}}}}
  # read input and call solve
test_cases:
  - input: "..."
    expected: "..."
hidden_tests:
  - input: "..."
    expected: "..."""

    try:
        response = llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        # Parse YAML response
        import yaml
        content = response.content.strip()

        # Remove any markdown code fences
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n', '', content)
            content = re.sub(r'\n```$', '', content)

        data = yaml.safe_load(content)

        if data:
            return Challenge.from_dict(data)

    except Exception as e:
        print(f"Failed to generate challenge: {e}")

    return None
