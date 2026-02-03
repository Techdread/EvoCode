"""YAML challenge loader."""

from pathlib import Path
from typing import Optional
import yaml

from .models import Challenge, TestCase


def load_challenge(file_path: Path | str) -> Challenge:
    """
    Load a challenge from a YAML file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Challenge object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Challenge file not found: {file_path}")

    with open(file_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty or invalid YAML file: {file_path}")

    # Use filename as ID if not specified
    if "id" not in data:
        data["id"] = file_path.stem

    return Challenge.from_dict(data)


def load_challenges_from_directory(
    directory: Path | str,
    pattern: str = "*.yaml",
) -> list[Challenge]:
    """
    Load all challenges from a directory.

    Args:
        directory: Directory containing YAML files
        pattern: Glob pattern for challenge files

    Returns:
        List of Challenge objects
    """
    directory = Path(directory)

    if not directory.exists():
        return []

    challenges = []
    for file_path in sorted(directory.glob(pattern)):
        try:
            challenge = load_challenge(file_path)
            challenges.append(challenge)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")

    # Also try .yml extension
    if pattern == "*.yaml":
        for file_path in sorted(directory.glob("*.yml")):
            try:
                challenge = load_challenge(file_path)
                # Avoid duplicates
                if not any(c.id == challenge.id for c in challenges):
                    challenges.append(challenge)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")

    return challenges


def save_challenge(challenge: Challenge, file_path: Path | str):
    """
    Save a challenge to a YAML file.

    Args:
        challenge: Challenge object to save
        file_path: Path for the output file
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    data = challenge.to_dict()

    with open(file_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def sync_challenges_to_db(challenges_dir: Path | str, db) -> int:
    """
    Sync challenges from YAML files to database.

    Args:
        challenges_dir: Directory containing challenge YAML files
        db: Database instance

    Returns:
        Number of challenges synced
    """
    challenges = load_challenges_from_directory(challenges_dir)
    count = 0

    for challenge in challenges:
        # Add/update challenge
        db.add_challenge(
            challenge_id=challenge.id,
            name=challenge.name,
            description=challenge.description,
            language=challenge.language,
            difficulty=challenge.difficulty,
            runner=challenge.runner,
            template=challenge.template,
        )

        # Clear and re-add test cases
        db.clear_test_cases(challenge.id)

        for tc in challenge.test_cases:
            db.add_test_case(
                challenge_id=challenge.id,
                input_data=tc.input,
                expected=tc.expected,
                is_hidden=False,
            )

        for tc in challenge.hidden_tests:
            db.add_test_case(
                challenge_id=challenge.id,
                input_data=tc.input,
                expected=tc.expected,
                is_hidden=True,
            )

        count += 1

    return count
