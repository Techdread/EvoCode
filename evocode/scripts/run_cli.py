#!/usr/bin/env python3
"""CLI tool to run evaluations without the Streamlit UI."""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import get_database
from core.llm import LLMConfig, create_provider
from core.judge import Judge0Client
from core.challenges.loader import load_challenges_from_directory
from core.evaluation import EvaluationRunner


def main():
    parser = argparse.ArgumentParser(description="Run EvoCode evaluation from CLI")
    parser.add_argument("challenge", nargs="?", help="Challenge ID to run")
    parser.add_argument("--model", "-m", type=int, help="Model ID from database")
    parser.add_argument("--endpoint", "-e", default="http://localhost:1234/v1", help="LLM endpoint URL")
    parser.add_argument("--judge0", "-j", default="http://localhost:2358", help="Judge0 URL")
    parser.add_argument("--attempts", "-a", type=int, default=10, help="Max attempts")
    parser.add_argument("--list-challenges", "-l", action="store_true", help="List available challenges")
    parser.add_argument("--list-models", action="store_true", help="List configured models")

    args = parser.parse_args()

    db = get_database()

    # List challenges
    if args.list_challenges:
        challenges_dir = Path(__file__).parent.parent / "challenges"
        challenges = load_challenges_from_directory(challenges_dir)
        print("Available challenges:")
        for c in challenges:
            print(f"  {c.id}: {c.name} ({c.language}, {c.difficulty})")
        return

    # List models
    if args.list_models:
        models = db.get_models()
        if models:
            print("Configured models:")
            for m in models:
                print(f"  [{m['id']}] {m['display_name']} ({m['endpoint']})")
        else:
            print("No models configured. Use the Streamlit UI to add models.")
        return

    # Load challenge
    challenges_dir = Path(__file__).parent.parent / "challenges"
    challenges = {c.id: c for c in load_challenges_from_directory(challenges_dir)}

    if not args.challenge:
        print("Error: challenge argument required")
        print(f"Available: {', '.join(challenges.keys())}")
        return 1

    if args.challenge not in challenges:
        print(f"Challenge '{args.challenge}' not found.")
        print(f"Available: {', '.join(challenges.keys())}")
        return 1

    challenge = challenges[args.challenge]
    print(f"Challenge: {challenge.name} ({challenge.language})")

    # Get or create model
    model_id = args.model
    if model_id:
        model = db.get_model(model_id)
        if not model:
            print(f"Model ID {model_id} not found")
            return 1
        llm_config = LLMConfig(
            provider=model["provider"],
            endpoint=model["endpoint"],
            model_name=model["model_name"],
            api_key=model.get("api_key"),
        )
    else:
        # Use default config
        llm_config = LLMConfig(
            provider="lmstudio",
            endpoint=args.endpoint,
            model_name="default",
        )
        # Add to database
        model_id = db.add_model(
            provider="lmstudio",
            model_name="default",
            endpoint=args.endpoint,
            display_name="CLI Model",
        )

    # Create LLM provider
    llm = create_provider(llm_config)
    print(f"LLM: {llm_config.endpoint}")

    # Check LLM connection
    if not llm.health_check():
        print("ERROR: Cannot connect to LLM endpoint")
        return 1

    # Create Judge0 client
    judge = Judge0Client(base_url=args.judge0)
    print(f"Judge0: {args.judge0}")

    # Check Judge0 connection
    if not judge.health_check():
        print("ERROR: Cannot connect to Judge0")
        return 1

    print(f"Max attempts: {args.attempts}")
    print("-" * 50)

    # Progress callback
    def progress(attempt: int, fitness: float, status: str):
        if status == "generating":
            print(f"Attempt {attempt}: Generating code...")
        elif status == "tested":
            print(f"Attempt {attempt}: Fitness = {fitness:.0%}")

    # Run evaluation
    runner = EvaluationRunner(
        llm=llm,
        judge=judge,
        db=db,
        max_attempts=args.attempts,
    )

    result = runner.run(
        challenge=challenge,
        model_id=model_id,
        progress_callback=progress,
    )

    print("-" * 50)
    print(f"Status: {result.status.upper()}")
    print(f"Best fitness: {result.best_fitness:.0%}")
    print(f"Attempts used: {result.attempts_used}")
    print(f"Total tokens: {result.total_tokens_prompt + result.total_tokens_completion}")

    if result.final_code:
        print("\nBest solution:")
        print("-" * 50)
        print(result.final_code)

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
