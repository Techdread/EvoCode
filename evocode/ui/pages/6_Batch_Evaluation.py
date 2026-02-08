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
from core.llm import LLMConfig, create_provider, fetch_lmstudio_models, fetch_openrouter_models, get_openrouter_providers
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

    # Model source selection
    model_source = st.radio(
        "Model Source",
        ["Configured Models", "LM Studio Direct", "OpenRouter"],
        horizontal=True,
        key="model_source",
    )

    # Variables to track model selection
    selected_model_id = None
    model_info = None
    direct_endpoint = None
    direct_model_id = None
    use_server_defaults = False
    direct_provider = None
    direct_api_key = None

    if model_source == "LM Studio Direct":
        # LM Studio Direct Mode
        st.info("Using LM Studio's settings (temperature, max tokens, etc.)")

        col_endpoint, col_refresh = st.columns([4, 1])

        with col_endpoint:
            default_endpoint = config.get("llm", {}).get("providers", {}).get("lmstudio", {}).get("endpoint", "http://localhost:1234/v1")
            direct_endpoint = st.text_input(
                "LM Studio Endpoint",
                value=default_endpoint,
                key="lmstudio_endpoint",
            )

        with col_refresh:
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("🔄", key="refresh_lmstudio", help="Refresh model list")

        if direct_endpoint:
            with st.spinner("Fetching models..."):
                available_models = fetch_lmstudio_models(direct_endpoint)

            if available_models:
                model_names = [m.get("id", "unknown") for m in available_models]
                direct_model_id = st.selectbox(
                    "Available Models",
                    options=model_names,
                    key="lmstudio_model_select",
                )
                st.success(f"Found {len(model_names)} model(s)")
                use_server_defaults = True
                direct_provider = "lmstudio"
            else:
                st.error("Could not fetch models. Check if LM Studio is running.")

    elif model_source == "OpenRouter":
        # OpenRouter Mode
        st.info("Using OpenRouter - access to many models including free ones")

        # API Key
        openrouter_key = st.text_input(
            "OpenRouter API Key",
            value=st.session_state.get("openrouter_api_key", ""),
            type="password",
            key="openrouter_key_input",
            help="Get your key at https://openrouter.ai/keys",
        )

        if openrouter_key:
            st.session_state.openrouter_api_key = openrouter_key
            direct_api_key = openrouter_key

            # Filters
            col_f1, col_f2, col_f3 = st.columns(3)

            with col_f1:
                free_only = st.checkbox("Free models only", value=True, key="or_free")

            with col_f2:
                providers = get_openrouter_providers(openrouter_key)
                provider_filter = st.selectbox(
                    "Provider",
                    options=["All"] + providers,
                    key="or_provider",
                )

            with col_f3:
                search = st.text_input("Search", placeholder="llama, gpt...", key="or_search")

            # Fetch models
            with st.spinner("Fetching OpenRouter models..."):
                or_models = fetch_openrouter_models(
                    api_key=openrouter_key,
                    free_only=free_only,
                    provider_filter=provider_filter if provider_filter != "All" else None,
                    search=search if search else None,
                )

            if or_models:
                # Build display options
                model_options_or = {}
                for m in or_models:
                    mid = m.get("id", "unknown")
                    ctx = m.get("context_length", "?")
                    name = m.get("name", mid)
                    display = f"{name} ({ctx} ctx)"
                    model_options_or[display] = m

                selected_or = st.selectbox(
                    f"Model ({len(or_models)} available)",
                    options=list(model_options_or.keys()),
                    key="or_model_select",
                )

                if selected_or:
                    sel_model = model_options_or[selected_or]
                    direct_model_id = sel_model.get("id")
                    direct_endpoint = "https://openrouter.ai/api/v1"
                    direct_provider = "openrouter"
                    use_server_defaults = True

                    # Show pricing
                    pricing = sel_model.get("pricing", {})
                    st.caption(f"Pricing: ${pricing.get('prompt', '?')}/1K prompt, ${pricing.get('completion', '?')}/1K completion")
            else:
                st.warning("No models found matching filters.")
        else:
            st.warning("Enter your OpenRouter API key to browse models.")

    else:
        # Configured Models
        if not models:
            st.warning("No LLM models configured. Add one in Model Settings or use Direct modes above.")
        else:
            model_options = {m["display_name"]: m["id"] for m in models}
            selected_model_name = st.selectbox(
                "Configured Model",
                options=list(model_options.keys()),
            )
            selected_model_id = model_options[selected_model_name]

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

        # Only show temperature if not using server defaults
        if not use_server_defaults:
            temperature = st.slider(
                "Temperature",
                0.0,
                2.0,
                model_info.get("temperature", 0.7) if model_info else 0.7,
                0.1,
            )
        else:
            temperature = None  # Will use server defaults

        batch_name = st.text_input(
            "Batch Name (optional)",
            placeholder=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

    # Start button
    st.markdown("---")

    # Check if we have a valid model selection
    has_valid_model = (model_source != "Configured Models" and direct_model_id) or (model_source == "Configured Models" and selected_model_id)

    if not selected_challenge_ids:
        st.warning("Please select at least one challenge to run.")
    elif not has_valid_model:
        st.warning("Please select a model to run evaluations.")
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

                # Create LLM provider based on mode
                if model_source in ["LM Studio Direct", "OpenRouter"]:
                    # Direct Mode - create/get minimal model record for tracking
                    existing_models = db.get_models()
                    model_record = None
                    for m in existing_models:
                        if m["endpoint"] == direct_endpoint and m["model_name"] == direct_model_id:
                            model_record = m
                            break

                    if not model_record:
                        # Create a new model record for tracking
                        display_prefix = "LM Studio" if direct_provider == "lmstudio" else "OpenRouter"
                        new_model_id = db.add_model(
                            provider=direct_provider,
                            model_name=direct_model_id,
                            endpoint=direct_endpoint,
                            display_name=f"{display_prefix}: {direct_model_id}",
                            api_key=direct_api_key,
                            temperature=0.7,
                            max_tokens=2048,
                        )
                        selected_model_id = new_model_id
                    else:
                        selected_model_id = model_record["id"]

                    # Create config
                    llm_config = LLMConfig(
                        provider=direct_provider,
                        endpoint=direct_endpoint,
                        model_name=direct_model_id,
                        api_key=direct_api_key,
                        temperature=0.7,
                        max_tokens=2048,
                    )
                    llm = create_provider(llm_config)
                    llm._use_server_defaults = use_server_defaults
                else:
                    # Configured Models mode
                    llm_config = LLMConfig(
                        provider=model_info["provider"],
                        endpoint=model_info["endpoint"],
                        model_name=model_info["model_name"],
                        api_key=model_info.get("api_key"),
                        temperature=temperature,
                        max_tokens=model_info.get("max_tokens", 2048),
                    )
                    llm = create_provider(llm_config)
                    llm._use_server_defaults = False

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
                    model_id=selected_model_id,
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
            batch_status_emoji = "✅" if batch["status"] == "completed" and batch["successful_runs"] == batch["total_runs"] else "🔄" if batch["status"] == "running" else "⚠️"

            pass_rate = (batch["successful_runs"] / batch["completed_runs"] * 100) if batch["completed_runs"] > 0 else 0
            batch_name = batch["name"] or f"Batch #{batch['id']}"

            with st.expander(
                f"{batch_status_emoji} {batch_name} - "
                f"{batch['successful_runs']}/{batch['total_runs']} passed ({pass_rate:.0f}%)"
            ):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Runs", batch["total_runs"])
                col2.metric("Completed", batch["completed_runs"])
                col3.metric("Passed", batch["successful_runs"])
                col4.metric("Failed", batch["failed_runs"])

                # Model info section
                st.markdown("---")
                st.markdown("**Model:**")
                if batch.get("model_name"):
                    model_col1, model_col2 = st.columns(2)
                    with model_col1:
                        st.text(f"Name: {batch['model_name']}")
                        st.text(f"Provider: {batch.get('model_provider', 'Unknown')}")
                        st.text(f"Endpoint: {batch.get('model_endpoint', 'Unknown')}")
                    with model_col2:
                        # Check if using server defaults (LM Studio Direct)
                        if batch.get("model_name", "").startswith("LM Studio:"):
                            st.text("Settings: Server Defaults (LM Studio Direct)")
                        else:
                            temp = batch.get('model_temperature', 'N/A')
                            max_tok = batch.get('model_max_tokens', 'N/A')
                            st.text(f"Temperature: {temp}")
                            st.text(f"Max Tokens: {max_tok}")
                else:
                    st.text("Model: Unknown (older batch)")

                st.markdown("---")

                # Timing info
                st.text(f"Started: {batch['created_at']}")
                if batch["completed_at"]:
                    st.text(f"Completed: {batch['completed_at']}")
                    # Calculate duration
                    try:
                        from datetime import datetime
                        start = datetime.fromisoformat(batch['created_at'].replace(' ', 'T'))
                        end = datetime.fromisoformat(batch['completed_at'].replace(' ', 'T'))
                        duration = end - start
                        total_seconds = int(duration.total_seconds())
                        minutes, seconds = divmod(total_seconds, 60)
                        hours, minutes = divmod(minutes, 60)
                        if hours > 0:
                            duration_str = f"{hours}h {minutes}m {seconds}s"
                        elif minutes > 0:
                            duration_str = f"{minutes}m {seconds}s"
                        else:
                            duration_str = f"{seconds}s"
                        st.text(f"Duration: {duration_str}")
                    except Exception:
                        pass

                # Get batch runs
                batch_runs = db.get_batch_runs(batch["id"])

                if batch_runs:
                    # Tabs for Summary and Code Review
                    summary_tab, code_tab = st.tabs(["📊 Summary", "💻 Code Review"])

                    with summary_tab:
                        runs_data = []
                        for run in batch_runs:
                            run_status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "🔄"
                            runs_data.append({
                                "Status": run_status_emoji,
                                "Challenge": run["challenge_name"],
                                "Language": run["language"],
                                "Difficulty": run["difficulty"],
                                "Fitness": f"{run['best_fitness']:.0%}",
                                "Attempts": f"{run['attempts_used']}/{run['max_attempts']}",
                            })
                        df = pd.DataFrame(runs_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)

                    with code_tab:
                        # Filter options
                        filter_col1, filter_col2 = st.columns([1, 3])
                        with filter_col1:
                            code_filter = st.selectbox(
                                "Filter",
                                ["All", "Passed", "Failed"],
                                key=f"code_filter_{batch['id']}",
                            )

                        # Filter runs based on selection
                        filtered_runs = batch_runs
                        if code_filter == "Passed":
                            filtered_runs = [r for r in batch_runs if r["status"] == "success"]
                        elif code_filter == "Failed":
                            filtered_runs = [r for r in batch_runs if r["status"] == "failed"]

                        if not filtered_runs:
                            st.info(f"No {code_filter.lower()} runs to display.")
                        else:
                            for run in filtered_runs:
                                run_emoji = "✅" if run["status"] == "success" else "❌"
                                fitness_pct = f"{run['best_fitness']:.0%}"

                                with st.expander(
                                    f"{run_emoji} {run['challenge_name']} ({run['language']}) - {fitness_pct}",
                                    expanded=False,
                                ):
                                    # Get attempts for this run
                                    attempts = db.get_attempts(run["id"])

                                    if not attempts:
                                        st.warning("No code generated for this run.")
                                    else:
                                        # Find best attempt
                                        best_attempt = max(attempts, key=lambda a: a["fitness"])

                                        st.markdown(f"**Best Attempt** (#{best_attempt['attempt_number']}, Fitness: {best_attempt['fitness']:.0%})")
                                        st.code(best_attempt["code"], language=run["language"])

                                        # Show all attempts option
                                        if len(attempts) > 1:
                                            if st.checkbox(
                                                f"Show all {len(attempts)} attempts",
                                                key=f"show_all_{batch['id']}_{run['id']}",
                                            ):
                                                st.markdown("---")
                                                st.markdown("**All Attempts:**")
                                                for attempt in attempts:
                                                    attempt_emoji = "✅" if attempt["fitness"] == 1.0 else "❌"
                                                    st.markdown(
                                                        f"**{attempt_emoji} Attempt #{attempt['attempt_number']}** - "
                                                        f"Fitness: {attempt['fitness']:.0%} | "
                                                        f"Tokens: {attempt['tokens_prompt'] + attempt['tokens_completion']}"
                                                    )
                                                    st.code(attempt["code"], language=run["language"])

                                                    if attempt.get("feedback"):
                                                        st.caption(f"Feedback: {attempt['feedback']}")
