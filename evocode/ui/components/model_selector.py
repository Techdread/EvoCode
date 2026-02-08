"""Reusable model selector component with LM Studio and OpenRouter support."""

import streamlit as st
from typing import Optional, Tuple
import yaml
from pathlib import Path

from core.llm import (
    LLMConfig,
    create_provider,
    fetch_lmstudio_models,
    fetch_openrouter_models,
    get_openrouter_providers,
)


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_openrouter_api_key() -> Optional[str]:
    """Get OpenRouter API key from session state or config."""
    # Check session state first
    if "openrouter_api_key" in st.session_state and st.session_state.openrouter_api_key:
        return st.session_state.openrouter_api_key

    # Fall back to config
    config = load_config()
    return config.get("openrouter", {}).get("api_key")


def model_selector(
    key_prefix: str,
    show_configured: bool = True,
    show_lmstudio: bool = True,
    show_openrouter: bool = True,
    db=None,
) -> Tuple[Optional[LLMConfig], Optional[int], bool]:
    """
    Render a model selector component.

    Args:
        key_prefix: Unique prefix for Streamlit widget keys
        show_configured: Show configured models from database
        show_lmstudio: Show LM Studio Direct option
        show_openrouter: Show OpenRouter option
        db: Database instance for configured models

    Returns:
        Tuple of (LLMConfig or None, model_id or None, use_server_defaults)
    """
    config = load_config()

    # Mode selection
    modes = []
    if show_configured and db:
        modes.append("Configured Models")
    if show_lmstudio:
        modes.append("LM Studio Direct")
    if show_openrouter:
        modes.append("OpenRouter")

    if not modes:
        st.warning("No model sources available.")
        return None, None, False

    mode = st.radio(
        "Model Source",
        modes,
        horizontal=True,
        key=f"{key_prefix}_mode",
    )

    llm_config = None
    model_id = None
    use_server_defaults = False

    # === Configured Models ===
    if mode == "Configured Models" and db:
        models = db.get_models()
        if not models:
            st.warning("No models configured. Add one in Model Settings.")
        else:
            model_options = {m["display_name"]: m for m in models}
            selected_name = st.selectbox(
                "Model",
                options=list(model_options.keys()),
                key=f"{key_prefix}_configured_model",
            )
            model_info = model_options[selected_name]
            model_id = model_info["id"]

            st.caption(f"Provider: {model_info['provider']} | Endpoint: {model_info['endpoint']}")

            llm_config = LLMConfig(
                provider=model_info["provider"],
                endpoint=model_info["endpoint"],
                model_name=model_info["model_name"],
                api_key=model_info.get("api_key"),
                temperature=model_info.get("temperature", 0.7),
                max_tokens=model_info.get("max_tokens", 2048),
            )

    # === LM Studio Direct ===
    elif mode == "LM Studio Direct":
        st.info("Using LM Studio's server-side settings")

        default_endpoint = config.get("llm", {}).get("providers", {}).get("lmstudio", {}).get("endpoint", "http://localhost:1234/v1")

        col_endpoint, col_refresh = st.columns([4, 1])
        with col_endpoint:
            endpoint = st.text_input(
                "LM Studio Endpoint",
                value=default_endpoint,
                key=f"{key_prefix}_lmstudio_endpoint",
            )
        with col_refresh:
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("🔄", key=f"{key_prefix}_lmstudio_refresh", help="Refresh models")

        if endpoint:
            with st.spinner("Fetching models..."):
                models = fetch_lmstudio_models(endpoint)

            if models:
                model_names = [m.get("id", "unknown") for m in models]
                selected_model = st.selectbox(
                    "Model",
                    options=model_names,
                    key=f"{key_prefix}_lmstudio_model",
                )
                st.success(f"Found {len(model_names)} model(s)")

                llm_config = LLMConfig(
                    provider="lmstudio",
                    endpoint=endpoint,
                    model_name=selected_model,
                )
                use_server_defaults = True
            else:
                st.error("Could not fetch models. Is LM Studio running?")

    # === OpenRouter ===
    elif mode == "OpenRouter":
        # API Key input
        api_key = st.text_input(
            "OpenRouter API Key",
            value=get_openrouter_api_key() or "",
            type="password",
            key=f"{key_prefix}_openrouter_key",
            help="Get your key at https://openrouter.ai/keys",
        )

        if api_key:
            st.session_state.openrouter_api_key = api_key

            # Filters
            col_filter1, col_filter2, col_filter3 = st.columns(3)

            with col_filter1:
                free_only = st.checkbox(
                    "Free models only",
                    value=True,
                    key=f"{key_prefix}_openrouter_free",
                )

            with col_filter2:
                # Get providers for filter
                providers = get_openrouter_providers(api_key)
                provider_options = ["All"] + providers
                provider_filter = st.selectbox(
                    "Provider",
                    options=provider_options,
                    key=f"{key_prefix}_openrouter_provider",
                )

            with col_filter3:
                search = st.text_input(
                    "Search",
                    placeholder="e.g., llama, gpt",
                    key=f"{key_prefix}_openrouter_search",
                )

            # Fetch and filter models
            with st.spinner("Fetching models..."):
                models = fetch_openrouter_models(
                    api_key=api_key,
                    free_only=free_only,
                    provider_filter=provider_filter if provider_filter != "All" else None,
                    search=search if search else None,
                )

            if models:
                # Build display options with context length
                model_options = {}
                for m in models:
                    model_id_str = m.get("id", "unknown")
                    context = m.get("context_length", "?")
                    name = m.get("name", model_id_str)
                    display = f"{name} ({context} ctx)"
                    model_options[display] = m

                selected_display = st.selectbox(
                    f"Model ({len(models)} available)",
                    options=list(model_options.keys()),
                    key=f"{key_prefix}_openrouter_model",
                )

                if selected_display:
                    selected_model_info = model_options[selected_display]
                    selected_model_id = selected_model_info.get("id")

                    # Show pricing info
                    pricing = selected_model_info.get("pricing", {})
                    prompt_cost = pricing.get("prompt", "?")
                    completion_cost = pricing.get("completion", "?")
                    st.caption(f"Pricing: ${prompt_cost}/1K prompt, ${completion_cost}/1K completion")

                    llm_config = LLMConfig(
                        provider="openrouter",
                        endpoint="https://openrouter.ai/api/v1",
                        model_name=selected_model_id,
                        api_key=api_key,
                    )
                    use_server_defaults = True  # Let OpenRouter use defaults
            else:
                st.warning("No models found matching filters.")
        else:
            st.warning("Enter your OpenRouter API key to browse models.")

    return llm_config, model_id, use_server_defaults
