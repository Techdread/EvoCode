#!/usr/bin/env python3
"""Initialize the EvoCode database and sync challenges."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import get_database
from core.challenges.loader import sync_challenges_to_db


def main():
    print("Initializing EvoCode database...")

    # Initialize database (creates schema)
    db = get_database()
    print(f"Database created at: {db.db_path}")

    # Sync challenges from YAML files
    challenges_dir = Path(__file__).parent.parent / "challenges"
    if challenges_dir.exists():
        count = sync_challenges_to_db(challenges_dir, db)
        print(f"Synced {count} challenges from {challenges_dir}")
    else:
        print(f"No challenges directory found at {challenges_dir}")

    # Show summary
    challenges = db.get_challenges()
    models = db.get_models()

    print(f"\nDatabase Summary:")
    print(f"  Challenges: {len(challenges)}")
    print(f"  Models: {len(models)}")

    if challenges:
        print(f"\nAvailable challenges:")
        for c in challenges:
            test_cases = db.get_test_cases(c["id"])
            visible = len([t for t in test_cases if not t["is_hidden"]])
            hidden = len([t for t in test_cases if t["is_hidden"]])
            print(f"  - {c['name']} ({c['language']}, {c['difficulty']}) - {visible}+{hidden} tests")

    print("\nInitialization complete!")
    print("\nNext steps:")
    print("1. Configure an LLM model in the Settings page")
    print("2. Run: streamlit run ui/app.py")


if __name__ == "__main__":
    main()
