"""Batch Evaluation page - Run evaluations on multiple challenges."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import yaml
import time
from datetime import datetime

from storage import get_database
from core.llm import LLMConfig, create_provider
from core.judge import Judge0Client
from core.challenges.loader import load_challenges_from_directory
from core.evaluation import EvaluationRunner


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


st.title("📦 Batch Evaluation")

db = get_database()
config = load_config()

# Get available data
challenges = db.get_challenges()
models = db.get_models()
languages = db.get_distinct_languages()

if not challenges:
    st.warning("No challenges available. Please add challenges first.")
    st.stop()

if not models:
    st.warning("No LLM models configured. Please configure a model in Settings first.")
    st.stop()

# Tabs for running new batch vs viewing history
tab_new, tab_history = st.tabs(["New Batch Run", "Batch History"])

with tab_new:
    st.subheader("Configure Batch Run")

    # Filters section
    st.markdown("### Filter Challenges")
    col1, col2 = st.columns(2)

    with col1:
        selected_language = st.selectbox(
            "Language",
            options=["All"] + languages,
            help="Filter challenges by programming language",
        )

    with col2:
        selected_difficulty = st.selectbox(
            "Difficulty",
            options=["All", "easy", "medium", "hard"],
            help="Filter challenges by difficulty level",
        )

    # Apply filters
    filter_language = None if selected_language == "All" else selected_language
    filter_difficulty = None if selected_difficulty == "All" else selected_difficulty
    filtered_challenges = db.get_challenges_filtered(
        language=filter_language, difficulty=filter_difficulty
    )

    # Challenge selection
    st.markdown("### Select Challenges")

    if not filtered_challenges:
        st.warning("No challenges match the selected filters.")
        st.stop()

    # Select all checkbox
    select_all = st.checkbox(
        f"Select All ({len(filtered_challenges)} challenges)",
        value=False,
    )

    # Build challenge options
    challenge_options = {c["name"]: c["id"] for c in filtered_challenges}

    if select_all:
        default_selection = list(challenge_options.keys())
    else:
        default_selection = []

    selected_challenge_names = st.multiselect(
        "Challenges",
        options=list(challenge_options.keys()),
        default=default_selection,
        help="Select challenges to include in the batch",
    )

    selected_challenge_ids = [challenge_options[name] for name in selected_challenge_names]

    # Show selection summary
    if selected_challenge_names:
        # Count by difficulty
        selected_challenges_data = [c for c in filtered_challenges if c["id"] in selected_challenge_ids]
        difficulty_counts = {}
        for c in selected_challenges_data:
            diff = c["difficulty"]
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

        summary_parts = [f"{count} {diff}" for diff, count in sorted(difficulty_counts.items())]
        st.info(f"Selected: {len(selected_challenge_names)} challenges ({', '.join(summary_parts)})")

    # Model selection
    st.markdown("### Select Model")
    model_options = {m["display_name"]: m["id"] for m in models}
    selected_model_name = st.selectbox(
        "Model",
        options=list(model_options.keys()),
    )
    selected_model_id = model_options[selected_model_name]

    # Show model details
    model_info = db.get_model(selected_model_id)
    if model_info:
        st.markdown(f"**Provider:** {model_info['provider']} | **Endpoint:** {model_info['endpoint']}")

    # Advanced options
    with st.expander("Advanced Options"):
        eval_config = config.get("evaluation", {})
        max_attempts = st.number_input(
            "Max Attempts per Challenge",
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
        batch_name = st.text_input(
            "Batch Name (optional)",
            placeholder=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

    # Start button
    st.markdown("---")

    if not selected_challenge_ids:
        st.warning("Please select at least one challenge to run.")
    else:
        if st.button("Start Batch Evaluation", type="primary", use_container_width=True):
            # Create progress containers
            overall_status = st.empty()
            overall_progress = st.progress(0)
            current_challenge_status = st.empty()
            current_progress = st.progress(0)
            results_container = st.empty()

            # Results tracking
            results = []
            completed = 0
            successful = 0
            failed = 0

            try:
                # Initialize components
                overall_status.info("Initializing...")

                # Load challenges from YAML
                challenges_dir = Path(__file__).parent.parent.parent / "challenges"
                all_challenges = {c.id: c for c in load_challenges_from_directory(challenges_dir)}

                # Verify all selected challenges exist
                missing = [cid for cid in selected_challenge_ids if cid not in all_challenges]
                if missing:
                    st.error(f"Challenges not found in YAML files: {missing}")
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
                overall_status.info("Checking connections...")

                if not llm.health_check():
                    st.error("Cannot connect to LLM endpoint. Please check Settings.")
                    st.stop()

                if not judge.health_check():
                    st.error("Cannot connect to Judge0. Please start Judge0 services.")
                    st.stop()

                # Create batch run in database
                batch_display_name = batch_name or f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                batch_id = db.create_batch(
                    name=batch_display_name,
                    total_runs=len(selected_challenge_ids),
                )

                # Create runner
                runner = EvaluationRunner(
                    llm=llm,
                    judge=judge,
                    db=db,
                    max_attempts=max_attempts,
                )

                overall_status.info(f"Running batch: {batch_display_name}")

                # Run each challenge sequentially
                for i, challenge_id in enumerate(selected_challenge_ids):
                    challenge = all_challenges[challenge_id]

                    # Update overall progress
                    overall_progress.progress((i) / len(selected_challenge_ids))
                    current_challenge_status.info(
                        f"[{i+1}/{len(selected_challenge_ids)}] Running: {challenge.name}"
                    )
                    current_progress.progress(0)

                    # Progress callback for current challenge
                    def make_progress_callback(max_att):
                        def progress_callback(attempt: int, fitness: float, status: str):
                            current_progress.progress(attempt / max_att)
                        return progress_callback

                    try:
                        # Create run with batch_id
                        run_id = db.create_run_with_batch(
                            challenge_id=challenge_id,
                            model_id=selected_model_id,
                            batch_id=batch_id,
                            max_attempts=max_attempts,
                        )

                        # Run evaluation
                        result = runner.run(
                            challenge=challenge,
                            model_id=selected_model_id,
                            progress_callback=make_progress_callback(max_attempts),
                            run_id=run_id,
                        )

                        # Track results
                        completed += 1
                        if result.status == "success":
                            successful += 1
                            status_emoji = "✅"
                        else:
                            failed += 1
                            status_emoji = "❌"

                        results.append({
                            "Challenge": challenge.name,
                            "Language": challenge.language,
                            "Difficulty": challenge.difficulty,
                            "Status": status_emoji,
                            "Fitness": f"{result.best_fitness:.0%}",
                            "Attempts": result.attempts_used,
                            "Tokens": result.total_tokens_prompt + result.total_tokens_completion,
                        })

                        # Update batch progress in database
                        db.update_batch(
                            batch_id=batch_id,
                            completed_runs=completed,
                            successful_runs=successful,
                            failed_runs=failed,
                        )

                    except Exception as e:
                        completed += 1
                        failed += 1
                        results.append({
                            "Challenge": challenge.name,
                            "Language": challenge.language,
                            "Difficulty": challenge.difficulty,
                            "Status": "⚠️",
                            "Fitness": "Error",
                            "Attempts": 0,
                            "Tokens": 0,
                        })
                        st.warning(f"Error running {challenge.name}: {e}")

                    # Update results table
                    with results_container.container():
                        st.markdown("### Results")
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True, hide_index=True)

                # Mark batch as completed
                db.update_batch(
                    batch_id=batch_id,
                    status="completed",
                    completed=True,
                )

                # Final status
                overall_progress.progress(1.0)
                current_progress.progress(1.0)

                pass_rate = (successful / completed * 100) if completed > 0 else 0
                if successful == completed:
                    overall_status.success(
                        f"Batch completed! All {completed} challenges passed! 🎉"
                    )
                else:
                    overall_status.warning(
                        f"Batch completed: {successful}/{completed} passed ({pass_rate:.0f}%)"
                    )

                current_challenge_status.empty()

                # Summary metrics
                st.markdown("### Summary")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total", completed)
                col2.metric("Passed", successful)
                col3.metric("Failed", failed)
                col4.metric("Pass Rate", f"{pass_rate:.0f}%")

            except Exception as e:
                overall_status.error(f"Batch evaluation error: {e}")
                import traceback
                st.code(traceback.format_exc())

with tab_history:
    st.subheader("Previous Batch Runs")

    batches = db.get_batches(limit=20)

    if not batches:
        st.info("No batch runs yet. Start one in the 'New Batch Run' tab!")
    else:
        for batch in batches:
            status_emoji = "✅" if batch["status"] == "completed" and batch["successful_runs"] == batch["total_runs"] else "🔄" if batch["status"] == "running" else "⚠️"

            pass_rate = (batch["successful_runs"] / batch["completed_runs"] * 100) if batch["completed_runs"] > 0 else 0
            batch_name = batch["name"] or f"Batch #{batch['id']}"

            with st.expander(
                f"{status_emoji} {batch_name} - "
                f"{batch['successful_runs']}/{batch['total_runs']} passed ({pass_rate:.0f}%)"
            ):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Runs", batch["total_runs"])
                col2.metric("Completed", batch["completed_runs"])
                col3.metric("Passed", batch["successful_runs"])
                col4.metric("Failed", batch["failed_runs"])

                st.text(f"Started: {batch['created_at']}")
                if batch["completed_at"]:
                    st.text(f"Completed: {batch['completed_at']}")

                # Show individual runs in this batch
                batch_runs = db.get_batch_runs(batch["id"])
                if batch_runs:
                    st.markdown("**Individual Runs:**")
                    runs_data = []
                    for run in batch_runs:
                        status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "🔄"
                        runs_data.append({
                            "Status": status_emoji,
                            "Challenge": run["challenge_name"],
                            "Language": run["language"],
                            "Difficulty": run["difficulty"],
                            "Fitness": f"{run['best_fitness']:.0%}",
                            "Attempts": f"{run['attempts_used']}/{run['max_attempts']}",
                        })
                    df = pd.DataFrame(runs_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
