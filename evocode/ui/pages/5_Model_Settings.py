"""Settings page for configuring LLM endpoints and Judge0 connection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import yaml

from storage import get_database
from core.llm import LLMConfig, create_provider
from core.llm.base import (
    MIN_TOKENS, MAX_TOKENS, DEFAULT_TOKENS, TOKEN_STEP,
    MIN_TEMPERATURE, MAX_TEMPERATURE, DEFAULT_TEMPERATURE,
)
from core.judge import Judge0Client


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def save_config(config: dict):
    """Save configuration to config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


st.title("⚙️ Model Settings")

db = get_database()
config = load_config()

# Tabs for different settings
tab1, tab2, tab3 = st.tabs(["LLM Models", "Judge0", "General"])

# ============== LLM Models Tab ==============
with tab1:
    st.header("LLM Model Configuration")

    # Add new model form
    st.subheader("Add New Model")

    with st.form("add_model"):
        col1, col2 = st.columns(2)

        with col1:
            display_name = st.text_input("Display Name", placeholder="My Local Model")
            provider = st.selectbox("Provider", ["lmstudio", "openai", "local"])
            endpoint = st.text_input(
                "Endpoint URL",
                value="http://localhost:1234/v1",
                help="OpenAI-compatible API endpoint",
            )

        with col2:
            model_name = st.text_input(
                "Model Name",
                placeholder="default",
                help="Model identifier (for LM Studio, use 'default' or specific model name)",
            )
            api_key = st.text_input("API Key (optional)", type="password")
            temperature = st.slider("Temperature", MIN_TEMPERATURE, MAX_TEMPERATURE, DEFAULT_TEMPERATURE, 0.1)
            max_tokens = st.number_input("Max Tokens", MIN_TOKENS, MAX_TOKENS, DEFAULT_TOKENS, TOKEN_STEP)

        col_submit, col_test = st.columns(2)

        with col_submit:
            submitted = st.form_submit_button("Add Model", type="primary")

        if submitted and display_name and endpoint and model_name:
            model_id = db.add_model(
                provider=provider,
                model_name=model_name,
                endpoint=endpoint,
                display_name=display_name,
                api_key=api_key if api_key else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            st.success(f"Model '{display_name}' added successfully!")
            st.rerun()

    # Test connection button (outside form)
    st.subheader("Test Connection")
    test_col1, test_col2 = st.columns([3, 1])

    with test_col1:
        test_endpoint = st.text_input(
            "Test Endpoint",
            value="http://localhost:1234/v1",
            key="test_endpoint",
        )

    with test_col2:
        if st.button("Test LLM"):
            with st.spinner("Testing connection..."):
                try:
                    test_config = LLMConfig(
                        provider="lmstudio",
                        endpoint=test_endpoint,
                        model_name="default",
                    )
                    provider_instance = create_provider(test_config)
                    if provider_instance.health_check():
                        st.success("Connection successful!")
                        # Try to get models
                        if hasattr(provider_instance, "get_models"):
                            models = provider_instance.get_models()
                            if models:
                                st.info(f"Available models: {', '.join(models[:5])}")
                    else:
                        st.error("Connection failed - server not responding")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    # Existing models
    st.subheader("Configured Models")

    models = db.get_models()

    if not models:
        st.info("No models configured yet. Add one above!")
    else:
        for model in models:
            run_count = db.get_model_run_count(model["id"])
            label = f"**{model['display_name']}** ({model['provider']})"
            if run_count > 0:
                label += f" - {run_count} runs"

            with st.expander(label):
                # Check if we're editing this model
                editing_key = f"editing_model_{model['id']}"
                is_editing = st.session_state.get(editing_key, False)

                if is_editing:
                    # Edit form
                    with st.form(f"edit_form_{model['id']}"):
                        edit_display_name = st.text_input(
                            "Display Name",
                            value=model["display_name"],
                        )
                        edit_endpoint = st.text_input(
                            "Endpoint URL",
                            value=model["endpoint"],
                        )
                        edit_model_name = st.text_input(
                            "Model Name",
                            value=model["model_name"],
                        )
                        edit_api_key = st.text_input(
                            "API Key",
                            value=model.get("api_key") or "",
                            type="password",
                            help="Leave empty to keep existing key",
                        )
                        edit_temperature = st.slider(
                            "Temperature",
                            MIN_TEMPERATURE, MAX_TEMPERATURE,
                            float(model["temperature"]),
                            0.1,
                        )
                        edit_max_tokens = st.number_input(
                            "Max Tokens",
                            MIN_TOKENS, MAX_TOKENS,
                            int(model["max_tokens"]),
                            TOKEN_STEP,
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.form_submit_button("Save", type="primary"):
                                db.update_model(
                                    model_id=model["id"],
                                    display_name=edit_display_name,
                                    endpoint=edit_endpoint,
                                    model_name=edit_model_name,
                                    api_key=edit_api_key if edit_api_key else None,
                                    temperature=edit_temperature,
                                    max_tokens=edit_max_tokens,
                                )
                                st.session_state[editing_key] = False
                                st.success("Model updated!")
                                st.rerun()
                        with col_cancel:
                            if st.form_submit_button("Cancel"):
                                st.session_state[editing_key] = False
                                st.rerun()
                else:
                    # Display mode
                    st.text(f"Endpoint: {model['endpoint']}")
                    st.text(f"Model: {model['model_name']}")
                    st.text(f"Temperature: {model['temperature']}")
                    st.text(f"Max Tokens: {model['max_tokens']}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Test", key=f"test_{model['id']}"):
                            with st.spinner("Testing..."):
                                try:
                                    test_config = LLMConfig(
                                        provider=model["provider"],
                                        endpoint=model["endpoint"],
                                        model_name=model["model_name"],
                                        api_key=model.get("api_key"),
                                    )
                                    provider_instance = create_provider(test_config)
                                    if provider_instance.health_check():
                                        st.success("Connection OK!")
                                    else:
                                        st.error("Connection failed")
                                except Exception as e:
                                    st.error(f"Error: {e}")

                    with col2:
                        if st.button("Edit", key=f"edit_{model['id']}"):
                            st.session_state[editing_key] = True
                            st.rerun()

                    with col3:
                        delete_key = f"confirm_delete_{model['id']}"
                        if st.session_state.get(delete_key):
                            st.warning(f"This will delete {run_count} evaluation runs!")
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("Yes, delete", key=f"yes_del_{model['id']}", type="primary"):
                                    db.delete_model(model["id"], cascade=True)
                                    st.session_state[delete_key] = False
                                    st.success("Model deleted")
                                    st.rerun()
                            with col_no:
                                if st.button("Cancel", key=f"no_del_{model['id']}"):
                                    st.session_state[delete_key] = False
                                    st.rerun()
                        else:
                            if st.button("Delete", key=f"delete_{model['id']}", type="secondary"):
                                if run_count > 0:
                                    st.session_state[delete_key] = True
                                    st.rerun()
                                else:
                                    db.delete_model(model["id"])
                                    st.success("Model deleted")
                                    st.rerun()

# ============== Judge0 Tab ==============
with tab2:
    st.header("Judge0 Configuration")

    judge0_config = config.get("judge0", {})

    with st.form("judge0_config"):
        judge0_url = st.text_input(
            "Judge0 URL",
            value=judge0_config.get("base_url", "http://localhost:2358"),
        )
        judge0_timeout = st.number_input(
            "Timeout (seconds)",
            value=judge0_config.get("timeout", 30),
            min_value=5,
            max_value=120,
        )

        col1, col2 = st.columns(2)
        with col1:
            cpu_limit = st.number_input(
                "CPU Time Limit (seconds)",
                value=judge0_config.get("cpu_time_limit", 5.0),
                min_value=1.0,
                max_value=30.0,
                step=0.5,
            )
            memory_limit = st.number_input(
                "Memory Limit (KB)",
                value=judge0_config.get("memory_limit", 128000),
                min_value=16000,
                max_value=512000,
                step=16000,
            )

        with col2:
            wall_limit = st.number_input(
                "Wall Time Limit (seconds)",
                value=judge0_config.get("wall_time_limit", 15.0),
                min_value=5.0,
                max_value=60.0,
                step=1.0,
            )

        save_j0 = st.form_submit_button("Save Judge0 Settings")

        if save_j0:
            config["judge0"] = {
                "base_url": judge0_url,
                "timeout": judge0_timeout,
                "cpu_time_limit": cpu_limit,
                "wall_time_limit": wall_limit,
                "memory_limit": memory_limit,
            }
            save_config(config)
            st.success("Judge0 settings saved!")

    # Test Judge0 connection
    st.subheader("Test Judge0 Connection")

    if st.button("Test Judge0"):
        with st.spinner("Testing Judge0 connection..."):
            try:
                client = Judge0Client(
                    base_url=judge0_config.get("base_url", "http://localhost:2358"),
                    timeout=judge0_config.get("timeout", 30),
                )
                if client.health_check():
                    st.success("Judge0 is running!")

                    # Get languages
                    languages = client.get_languages()
                    st.info(f"Available languages: {len(languages)}")

                    # Test simple execution
                    result = client.submit(
                        source_code="print('Hello, EvoCode!')",
                        language="python",
                        wait=True,
                    )
                    if result.success and "Hello, EvoCode!" in result.stdout:
                        st.success("Test execution successful!")
                    else:
                        st.warning(f"Execution issue: {result.status}")
                else:
                    st.error("Judge0 is not responding")
            except Exception as e:
                st.error(f"Connection error: {e}")

# ============== General Tab ==============
with tab3:
    st.header("General Settings")

    eval_config = config.get("evaluation", {})

    with st.form("general_config"):
        max_attempts = st.number_input(
            "Default Max Attempts",
            value=eval_config.get("max_attempts", 10),
            min_value=1,
            max_value=50,
        )
        show_hidden = st.checkbox(
            "Show Hidden Tests in Results",
            value=eval_config.get("show_hidden_tests", False),
        )

        save_general = st.form_submit_button("Save General Settings")

        if save_general:
            config["evaluation"] = {
                "max_attempts": max_attempts,
                "show_hidden_tests": show_hidden,
            }
            save_config(config)
            st.success("General settings saved!")

    # Database info
    st.subheader("Database")

    db_path = Path(__file__).parent.parent.parent / "data" / "evocode.db"
    st.text(f"Location: {db_path}")

    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.text(f"Size: {size_mb:.2f} MB")

        challenges = db.get_challenges()
        runs = db.get_runs(limit=10000)
        st.text(f"Challenges: {len(challenges)}")
        st.text(f"Evaluation runs: {len(runs)}")

    # Reset database option
    st.subheader("Danger Zone")
    st.warning("These actions cannot be undone!")

    if st.button("Reset Database", type="secondary"):
        if st.checkbox("I understand this will delete all data"):
            if db_path.exists():
                db_path.unlink()
            st.success("Database reset. Refresh the page to reinitialize.")
