"""Run Evaluation page - Start evaluation runs and view live progress."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import yaml
import time

from storage import get_database
from core.llm import LLMConfig, create_provider
from core.judge import Judge0Client
from core.challenges import load_challenge
from core.challenges.loader import load_challenges_from_directory
from core.evaluation import EvaluationRunner


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


st.title("🚀 Run Evaluation")

db = get_database()
config = load_config()

# Get available challenges and models
challenges = db.get_challenges()
models = db.get_models()

if not challenges:
    st.warning("No challenges available. Please add challenges first.")
    st.stop()

if not models:
    st.warning("No LLM models configured. Please configure a model in Settings first.")
    st.stop()

# Selection form
st.subheader("Configure Run")

col1, col2 = st.columns(2)

with col1:
    challenge_options = {c["name"]: c["id"] for c in challenges}
    selected_challenge_name = st.selectbox(
        "Select Challenge",
        options=list(challenge_options.keys()),
    )
    selected_challenge_id = challenge_options[selected_challenge_name]

    # Show challenge details
    challenge_info = db.get_challenge(selected_challenge_id)
    if challenge_info:
        st.markdown(f"**Language:** {challenge_info['language']}")
        st.markdown(f"**Difficulty:** {challenge_info['difficulty']}")
        test_cases = db.get_test_cases(selected_challenge_id)
        visible = len([t for t in test_cases if not t["is_hidden"]])
        hidden = len([t for t in test_cases if t["is_hidden"]])
        st.markdown(f"**Tests:** {visible} visible, {hidden} hidden")

with col2:
    model_options = {m["display_name"]: m["id"] for m in models}
    selected_model_name = st.selectbox(
        "Select Model",
        options=list(model_options.keys()),
    )
    selected_model_id = model_options[selected_model_name]

    # Show model details
    model_info = db.get_model(selected_model_id)
    if model_info:
        st.markdown(f"**Provider:** {model_info['provider']}")
        st.markdown(f"**Endpoint:** {model_info['endpoint']}")

# Advanced options
with st.expander("Advanced Options"):
    eval_config = config.get("evaluation", {})
    max_attempts = st.number_input(
        "Max Attempts",
        value=eval_config.get("max_attempts", 10),
        min_value=1,
        max_value=50,
    )
    temperature = st.slider(
        "Temperature",
        0.0,
        2.0,
        model_info.get("temperature", 0.7) if model_info else 0.7,
        0.1,
    )

# Start button
st.markdown("---")

if st.button("Start Evaluation", type="primary", use_container_width=True):
    # Create progress containers
    status_container = st.empty()
    progress_bar = st.progress(0)
    metrics_container = st.empty()
    code_container = st.empty()
    results_container = st.empty()

    try:
        # Initialize components
        status_container.info("Initializing...")

        # Load challenge from YAML
        challenges_dir = Path(__file__).parent.parent.parent / "challenges"
        challenge = None
        for c in load_challenges_from_directory(challenges_dir):
            if c.id == selected_challenge_id:
                challenge = c
                break

        if not challenge:
            st.error(f"Challenge '{selected_challenge_id}' not found in YAML files")
            st.stop()

        # Create LLM provider
        llm_config = LLMConfig(
            provider=model_info["provider"],
            endpoint=model_info["endpoint"],
            model_name=model_info["model_name"],
            api_key=model_info.get("api_key"),
            temperature=temperature,
            max_tokens=model_info.get("max_tokens", 2048),
        )
        llm = create_provider(llm_config)

        # Create Judge0 client
        judge0_config = config.get("judge0", {})
        judge = Judge0Client(
            base_url=judge0_config.get("base_url", "http://localhost:2358"),
            timeout=judge0_config.get("timeout", 30),
        )

        # Check connections
        status_container.info("Checking connections...")

        if not llm.health_check():
            st.error("Cannot connect to LLM endpoint. Please check Settings.")
            st.stop()

        if not judge.health_check():
            st.error("Cannot connect to Judge0. Please start Judge0 services.")
            st.stop()

        # Create runner
        runner = EvaluationRunner(
            llm=llm,
            judge=judge,
            db=db,
            max_attempts=max_attempts,
        )

        # Progress tracking (use dict for mutable state in callback)
        progress_state = {"attempt": 0, "fitness": 0.0}

        def progress_callback(attempt: int, fitness: float, status: str):
            progress_state["attempt"] = attempt
            progress_state["fitness"] = fitness

            progress_bar.progress(attempt / max_attempts)

            if status == "generating":
                status_container.info(f"Attempt {attempt}/{max_attempts}: Generating code...")
            elif status == "tested":
                status_container.info(f"Attempt {attempt}/{max_attempts}: Tested - Fitness: {fitness:.0%}")

                # Update metrics
                with metrics_container.container():
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Attempt", f"{attempt}/{max_attempts}")
                    m2.metric("Best Fitness", f"{fitness:.0%}")
                    m3.metric("Status", "Running" if fitness < 1.0 else "Passed!")

        # Run evaluation
        status_container.info("Starting evaluation...")
        result = runner.run(
            challenge=challenge,
            model_id=selected_model_id,
            progress_callback=progress_callback,
        )

        # Show final results
        progress_bar.progress(1.0)

        if result.status == "success":
            status_container.success(f"Challenge solved in {result.attempts_used} attempt(s)!")
        elif result.status == "failed":
            status_container.error(f"Failed after {result.attempts_used} attempts. Best fitness: {result.best_fitness:.0%}")
        else:
            status_container.error(f"Error: {result.error_message}")

        # Update final metrics
        with metrics_container.container():
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Final Status", result.status.upper())
            m2.metric("Best Fitness", f"{result.best_fitness:.0%}")
            m3.metric("Attempts Used", result.attempts_used)
            m4.metric("Total Tokens", result.total_tokens_prompt + result.total_tokens_completion)

        # Show final code
        if result.final_code:
            with code_container.container():
                st.subheader("Best Solution")
                st.code(result.final_code, language=challenge.language)

        # Show attempt history
        if result.attempts:
            with results_container.container():
                st.subheader("Attempt History")

                # Tabs for different views
                tab_attempts, tab_evolution, tab_tests = st.tabs(["All Attempts", "Code Evolution", "Test Details"])

                with tab_attempts:
                    for attempt in result.attempts:
                        status_icon = "✅" if attempt.passed else "❌"
                        with st.expander(f"{status_icon} Attempt {attempt.attempt_number} - Fitness: {attempt.fitness:.0%}", expanded=(attempt.attempt_number == result.attempts_used)):
                            col1, col2, col3 = st.columns(3)
                            passed = sum(1 for t in attempt.test_results if t.passed)
                            total = len(attempt.test_results)
                            col1.metric("Tests Passed", f"{passed}/{total}")
                            col2.metric("Latency", f"{attempt.llm_response.latency_ms}ms")
                            col3.metric("Tokens", attempt.llm_response.tokens_prompt + attempt.llm_response.tokens_completion)

                            st.markdown("**Generated Code:**")
                            st.code(attempt.code, language=challenge.language)

                            # Show all test results
                            st.markdown("**Test Results:**")
                            for i, t in enumerate(attempt.test_results):
                                icon = "✅" if t.passed else "❌"
                                with st.container():
                                    input_preview = t.input[:30] + "..." if len(t.input) > 30 else t.input
                                    if t.passed:
                                        st.markdown(f"{icon} **Test {i+1}**: `{input_preview}` → `{t.expected}`")
                                    else:
                                        st.markdown(f"{icon} **Test {i+1}**: `{input_preview}`")
                                        st.markdown(f"   Expected: `{t.expected}` | Got: `{t.actual}`")
                                        if t.execution.stderr:
                                            st.markdown(f"   Error: `{t.execution.stderr[:100]}`")

                with tab_evolution:
                    st.markdown("**How the code evolved across attempts:**")

                    for i, attempt in enumerate(result.attempts):
                        status_icon = "✅" if attempt.passed else "❌"
                        st.markdown(f"### {status_icon} Attempt {attempt.attempt_number} ({attempt.fitness:.0%})")

                        # Show what changed from previous attempt
                        if i > 0:
                            prev_code = result.attempts[i-1].code
                            if attempt.code != prev_code:
                                prev_lines = set(prev_code.strip().split('\n'))
                                curr_lines = set(attempt.code.strip().split('\n'))
                                added = curr_lines - prev_lines
                                removed = prev_lines - curr_lines
                                if added or removed:
                                    st.markdown(f"*Changed {len(added)} lines added, {len(removed)} lines removed*")

                        st.code(attempt.code, language=challenge.language)

                        # Show feedback that led to next attempt
                        if not attempt.passed and i < len(result.attempts) - 1:
                            failures = [t for t in attempt.test_results if not t.passed]
                            if failures:
                                st.markdown("**Feedback given to LLM:**")
                                st.info(f"{len(failures)} tests failed. First failure: expected '{failures[0].expected}', got '{failures[0].actual}'")

                        st.markdown("---")

                with tab_tests:
                    st.markdown("**Test results across all attempts:**")

                    # Build test results table
                    if result.attempts and result.attempts[0].test_results:
                        test_data = []
                        for i, tc in enumerate(result.attempts[0].test_results):
                            row = {
                                "Test": i + 1,
                                "Input": tc.input[:25] + "..." if len(tc.input) > 25 else tc.input,
                                "Expected": tc.expected[:20] if len(tc.expected) <= 20 else tc.expected[:20] + "...",
                            }
                            for attempt in result.attempts:
                                if i < len(attempt.test_results):
                                    row[f"Att {attempt.attempt_number}"] = "✅" if attempt.test_results[i].passed else "❌"
                            test_data.append(row)

                        df = pd.DataFrame(test_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Evaluation error: {e}")
        import traceback
        st.code(traceback.format_exc())

# Recent runs section
st.markdown("---")
st.subheader("Recent Runs")

recent_runs = db.get_recent_runs(limit=10)

if recent_runs:
    for run in recent_runs:
        status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⚠️"

        with st.expander(f"{status_emoji} {run['challenge_name']} - {run['model_name']}"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Fitness", f"{run['best_fitness']:.0%}")
            col2.metric("Attempts", f"{run['attempts_used']}/{run['max_attempts']}")
            col3.metric("Tokens", run["total_tokens"])

            st.text(f"Started: {run['started_at']}")
            if run["duration_seconds"]:
                st.text(f"Duration: {run['duration_seconds']:.1f}s")

            # Show attempts inline
            attempts = db.get_attempts(run["run_id"])
            if attempts:
                st.markdown("**Attempts:**")
                for attempt in attempts:
                    status_icon = "✅" if attempt["fitness"] == 1.0 else "❌"
                    with st.expander(f"{status_icon} Attempt {attempt['attempt_number']} - Fitness: {attempt['fitness']:.0%}"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Latency", f"{attempt['llm_latency_ms']}ms")
                        col2.metric("Exec Time", f"{attempt['execution_time_ms']}ms")
                        col3.metric("Tokens", attempt['tokens_prompt'] + attempt['tokens_completion'])

                        st.markdown("**Code:**")
                        st.code(attempt["code"], language=run["language"])

                        # Show feedback/errors if any
                        if attempt.get("feedback"):
                            st.markdown("**Feedback:**")
                            st.warning(attempt["feedback"])

                        # Show test results from database
                        test_results = db.get_test_results(attempt["id"])
                        if test_results:
                            passed = sum(1 for t in test_results if t["passed"])
                            st.markdown(f"**Test Results:** {passed}/{len(test_results)} passed")

                            for i, tr in enumerate(test_results):
                                icon = "✅" if tr["passed"] else "❌"
                                stdout_preview = (tr["stdout"] or "")[:30]
                                st.markdown(f"{icon} Test {i+1}: output=`{stdout_preview}`")
else:
    st.info("No evaluation runs yet. Start one above!")
