"""Challenges page - Browse and manage coding challenges."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import yaml

from storage import get_database
from core.challenges import Challenge, TestCase, save_challenge
from core.challenges.loader import sync_challenges_to_db


st.title("📝 Challenges")

db = get_database()

# Tabs
tab1, tab2 = st.tabs(["Browse Challenges", "Create Challenge"])

# ============== Browse Tab ==============
with tab1:
    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        difficulty_filter = st.selectbox(
            "Difficulty",
            ["All", "easy", "medium", "hard"],
        )

    with col2:
        # Get unique languages
        challenges = db.get_challenges()
        languages = list(set(c["language"] for c in challenges))
        language_filter = st.selectbox(
            "Language",
            ["All"] + sorted(languages),
        )

    with col3:
        search = st.text_input("Search", placeholder="Search challenges...")

    # Get challenge statistics
    challenge_stats = {s["challenge_id"]: s for s in db.get_challenge_stats()}

    # Filter challenges
    filtered = challenges
    if difficulty_filter != "All":
        filtered = [c for c in filtered if c["difficulty"] == difficulty_filter]
    if language_filter != "All":
        filtered = [c for c in filtered if c["language"] == language_filter]
    if search:
        search_lower = search.lower()
        filtered = [c for c in filtered if search_lower in c["name"].lower() or search_lower in c["description"].lower()]

    st.markdown(f"**{len(filtered)} challenges found**")

    # Display challenges
    if not filtered:
        st.info("No challenges match your filters.")
    else:
        for challenge in filtered:
            stats = challenge_stats.get(challenge["id"], {})

            # Header with difficulty badge
            diff_colors = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
            diff_badge = diff_colors.get(challenge["difficulty"], "⚪")

            with st.expander(f"{diff_badge} **{challenge['name']}** ({challenge['language']})"):
                # Description
                st.markdown(challenge["description"][:500] + ("..." if len(challenge["description"]) > 500 else ""))

                # Metrics row
                col1, col2, col3, col4 = st.columns(4)

                col1.metric("Difficulty", challenge["difficulty"].capitalize())
                col2.metric("Language", challenge["language"])
                col3.metric(
                    "Tests",
                    f"{stats.get('visible_tests', 0)} + {stats.get('hidden_tests', 0)} hidden"
                )
                col4.metric(
                    "Pass Rate",
                    f"{stats.get('pass_rate', 0):.0f}%" if stats.get("pass_rate") else "N/A"
                )

                # Additional stats if available
                if stats.get("total_runs"):
                    st.markdown(f"**Runs:** {stats['total_runs']} total, {stats['successful_runs']} successful")
                    if stats.get("avg_attempts_to_solve"):
                        st.markdown(f"**Avg attempts to solve:** {stats['avg_attempts_to_solve']:.1f}")

                # Show test cases
                test_cases = db.get_test_cases(challenge["id"], include_hidden=False)
                if test_cases:
                    st.markdown("**Example Test Cases:**")
                    for i, tc in enumerate(test_cases[:3], 1):
                        st.markdown(f"{i}. Input: `{tc['input'][:50]}` → Output: `{tc['expected'][:50]}`")

                # Template if available
                if challenge.get("template"):
                    st.markdown("**Template:**")
                    st.code(challenge["template"], language=challenge["language"])

                # Actions
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Run Evaluation", key=f"run_{challenge['id']}", use_container_width=True):
                        st.session_state.selected_challenge = challenge["id"]
                        st.switch_page("pages/2_Run_Evaluation.py")

                with col2:
                    if st.button("Delete", key=f"delete_{challenge['id']}", type="secondary", use_container_width=True):
                        db.delete_challenge(challenge["id"])
                        st.success(f"Challenge '{challenge['name']}' deleted")
                        st.rerun()

# ============== Create Tab ==============
with tab2:
    st.subheader("Create New Challenge")

    with st.form("create_challenge"):
        # Basic info
        col1, col2 = st.columns(2)

        with col1:
            challenge_id = st.text_input(
                "Challenge ID",
                placeholder="two_sum",
                help="Unique identifier (lowercase, underscores)"
            )
            name = st.text_input(
                "Name",
                placeholder="Two Sum Problem"
            )
            language = st.selectbox(
                "Language",
                ["python", "javascript", "cpp", "java", "go", "rust", "ruby"],
            )

        with col2:
            difficulty = st.selectbox(
                "Difficulty",
                ["easy", "medium", "hard"],
                index=1,
            )

        # Description
        description = st.text_area(
            "Description",
            height=200,
            placeholder="Write a detailed problem description...\n\nInclude:\n- What the function should do\n- Input format\n- Output format\n- Constraints",
        )

        # Code templates
        st.markdown("### Code Templates")

        template = st.text_area(
            "Starting Template (optional)",
            height=100,
            placeholder="def solve(n):\n    pass",
            help="Initial code provided to the LLM",
        )

        runner = st.text_area(
            "Runner Template",
            height=150,
            value="{{solution}}\n\n# Read input and call solution\nn = int(input())\nprint(solve(n))",
            help="Template that wraps the solution. Use {{solution}} as placeholder.",
        )

        # Test cases
        st.markdown("### Test Cases")

        test_cases_raw = st.text_area(
            "Visible Test Cases",
            height=150,
            placeholder="1|1\n4|IV\n9|IX",
            help="One test per line, format: input|expected",
        )

        hidden_tests_raw = st.text_area(
            "Hidden Test Cases",
            height=150,
            placeholder="999|CMXCIX\n3999|MMMCMXCIX",
            help="One test per line, format: input|expected",
        )

        # Submit
        submitted = st.form_submit_button("Create Challenge", type="primary")

        if submitted:
            if not all([challenge_id, name, description, runner]):
                st.error("Please fill in all required fields")
            else:
                # Parse test cases
                def parse_tests(raw: str, hidden: bool = False) -> list[TestCase]:
                    tests = []
                    for line in raw.strip().split("\n"):
                        if "|" in line:
                            parts = line.split("|", 1)
                            tests.append(TestCase(
                                input=parts[0].strip(),
                                expected=parts[1].strip(),
                                is_hidden=hidden,
                            ))
                    return tests

                test_cases = parse_tests(test_cases_raw, False)
                hidden_tests = parse_tests(hidden_tests_raw, True)

                if not test_cases and not hidden_tests:
                    st.error("Please add at least one test case")
                else:
                    # Create challenge
                    challenge = Challenge(
                        id=challenge_id,
                        name=name,
                        description=description,
                        language=language,
                        difficulty=difficulty,
                        runner=runner,
                        template=template if template else None,
                        test_cases=test_cases,
                        hidden_tests=hidden_tests,
                    )

                    # Save to YAML
                    challenges_dir = Path(__file__).parent.parent.parent / "challenges"
                    challenges_dir.mkdir(exist_ok=True)
                    save_challenge(challenge, challenges_dir / f"{challenge_id}.yaml")

                    # Sync to database
                    sync_challenges_to_db(challenges_dir, db)

                    st.success(f"Challenge '{name}' created successfully!")
                    st.rerun()

    # Example templates
    st.markdown("---")
    st.subheader("Example Templates")

    with st.expander("Python Function Template"):
        st.code("""
id: example_problem
name: "Example Problem"
language: python
difficulty: medium
description: |
  Write a function solve(n) that...

template: |
  def solve(n: int) -> int:
      pass

runner: |
  {{solution}}
  n = int(input())
  print(solve(n))

test_cases:
  - input: "1"
    expected: "1"
  - input: "5"
    expected: "120"

hidden_tests:
  - input: "10"
    expected: "3628800"
""", language="yaml")

    with st.expander("JavaScript Template"):
        st.code("""
id: js_example
name: "JS Example"
language: javascript
difficulty: easy
description: |
  Write a function solve(n) that...

runner: |
  {{solution}}
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin });
  rl.on('line', (line) => {
    console.log(solve(parseInt(line)));
    rl.close();
  });

test_cases:
  - input: "5"
    expected: "25"
""", language="yaml")
