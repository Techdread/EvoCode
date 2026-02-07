"""Code Playground - Run, test, and debug code with LLM assistance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import yaml

from storage import get_database
from core.llm import LLMConfig, create_provider, fetch_lmstudio_models
from core.judge import Judge0Client, LANGUAGE_IDS


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


st.title("🛝 Code Playground")
st.markdown("*Run, test, and debug code with LLM assistance*")

db = get_database()
config = load_config()

# Initialize session state
if "playground_code" not in st.session_state:
    st.session_state.playground_code = ""
if "playground_language" not in st.session_state:
    st.session_state.playground_language = "python"
if "playground_output" not in st.session_state:
    st.session_state.playground_output = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Layout: Main area + Sidebar for LLM
col_main, col_llm = st.columns([3, 2])

with col_main:
    # Code source selection
    st.subheader("📝 Code Editor")

    source_tab, history_tab = st.tabs(["Write Code", "Load from History"])

    with source_tab:
        # Language selector
        language = st.selectbox(
            "Language",
            options=sorted(LANGUAGE_IDS.keys()),
            index=sorted(LANGUAGE_IDS.keys()).index(st.session_state.playground_language)
                  if st.session_state.playground_language in LANGUAGE_IDS else 0,
            key="lang_select",
        )
        st.session_state.playground_language = language

        # Code editor
        code = st.text_area(
            "Code",
            value=st.session_state.playground_code,
            height=300,
            key="code_editor",
            help="Write or paste your code here",
        )
        st.session_state.playground_code = code

    with history_tab:
        # Load from evaluation history
        st.markdown("**Load code from previous evaluations:**")

        # Get recent runs
        recent_runs = db.get_recent_runs(limit=50)

        if not recent_runs:
            st.info("No evaluation history yet.")
        else:
            # Group by challenge
            run_options = {}
            for run in recent_runs:
                label = f"{run['challenge_name']} ({run['model_name']}) - {run['status']}"
                run_options[label] = run

            selected_run_label = st.selectbox(
                "Select Run",
                options=list(run_options.keys()),
                key="history_run_select",
            )

            if selected_run_label:
                selected_run = run_options[selected_run_label]

                # Get attempts for this run
                attempts = db.get_attempts(selected_run["run_id"])

                if attempts:
                    attempt_options = {
                        f"Attempt {a['attempt_number']} - {a['fitness']:.0%}": a
                        for a in attempts
                    }

                    selected_attempt_label = st.selectbox(
                        "Select Attempt",
                        options=list(attempt_options.keys()),
                        key="history_attempt_select",
                    )

                    if selected_attempt_label:
                        selected_attempt = attempt_options[selected_attempt_label]

                        st.code(selected_attempt["code"], language=selected_run["language"])

                        if st.button("Load this code", key="load_history"):
                            st.session_state.playground_code = selected_attempt["code"]
                            st.session_state.playground_language = selected_run["language"]
                            st.rerun()

    # Test input section
    st.markdown("---")
    st.subheader("🧪 Test Runner")

    input_mode = st.radio(
        "Input Mode",
        ["Custom Input", "From Challenge"],
        horizontal=True,
    )

    if input_mode == "Custom Input":
        test_input = st.text_area(
            "Input (stdin)",
            height=100,
            placeholder="Enter test input here...",
            key="custom_input",
        )
        expected_output = st.text_input(
            "Expected Output (optional)",
            placeholder="Leave empty to just see output",
            key="expected_output",
        )
        test_cases_to_run = [{"input": test_input, "expected": expected_output}] if test_input else []
    else:
        # Load test cases from a challenge
        challenges = db.get_challenges()
        if challenges:
            challenge_options = {c["name"]: c["id"] for c in challenges}
            selected_challenge_name = st.selectbox(
                "Select Challenge",
                options=list(challenge_options.keys()),
                key="challenge_select",
            )
            challenge_id = challenge_options[selected_challenge_name]

            # Get test cases
            test_cases = db.get_test_cases(challenge_id)
            visible_tests = [t for t in test_cases if not t["is_hidden"]]
            hidden_tests = [t for t in test_cases if t["is_hidden"]]

            st.markdown(f"**{len(visible_tests)} visible, {len(hidden_tests)} hidden tests**")

            include_hidden = st.checkbox("Include hidden tests", value=False)

            test_cases_to_run = visible_tests + (hidden_tests if include_hidden else [])

            # Show test cases
            with st.expander("View test cases"):
                for i, tc in enumerate(test_cases_to_run):
                    hidden_badge = " (hidden)" if tc.get("is_hidden") else ""
                    st.markdown(f"**Test {i+1}{hidden_badge}:**")
                    st.text(f"Input: {tc['input'][:100]}...")
                    st.text(f"Expected: {tc['expected']}")
        else:
            st.warning("No challenges available.")
            test_cases_to_run = []

    # Run button
    col_run, col_clear = st.columns(2)

    with col_run:
        run_clicked = st.button("▶️ Run Code", type="primary", use_container_width=True)

    with col_clear:
        if st.button("🗑️ Clear Output", use_container_width=True):
            st.session_state.playground_output = None
            st.rerun()

    # Execute code
    if run_clicked and st.session_state.playground_code:
        with st.spinner("Running code..."):
            try:
                judge0_config = config.get("judge0", {})
                judge = Judge0Client(
                    base_url=judge0_config.get("base_url", "http://localhost:2358"),
                    timeout=judge0_config.get("timeout", 30),
                )

                if not judge.health_check():
                    st.error("Judge0 is not running. Please start Judge0 services.")
                else:
                    results = []

                    if not test_cases_to_run:
                        # Run with no input
                        result = judge.submit(
                            source_code=st.session_state.playground_code,
                            language=st.session_state.playground_language,
                            stdin="",
                            wait=True,
                        )
                        results.append({
                            "input": "(no input)",
                            "expected": None,
                            "result": result,
                        })
                    else:
                        # Run against test cases
                        for tc in test_cases_to_run:
                            result = judge.submit(
                                source_code=st.session_state.playground_code,
                                language=st.session_state.playground_language,
                                stdin=tc["input"],
                                wait=True,
                            )
                            results.append({
                                "input": tc["input"],
                                "expected": tc.get("expected"),
                                "result": result,
                            })

                    st.session_state.playground_output = results

            except Exception as e:
                st.error(f"Error: {e}")

    # Display output
    if st.session_state.playground_output:
        st.markdown("---")
        st.subheader("📤 Output")

        results = st.session_state.playground_output

        passed = 0
        total = len(results)

        for i, r in enumerate(results):
            result = r["result"]
            expected = r["expected"]

            # Check if passed
            actual_output = (result.stdout or "").strip()
            expected_output = (expected or "").strip()
            is_pass = expected and actual_output == expected_output

            if is_pass:
                passed += 1

            icon = "✅" if is_pass else "❌" if expected else "ℹ️"

            with st.expander(f"{icon} Test {i+1}", expanded=(len(results) == 1 or not is_pass)):
                col1, col2, col3 = st.columns(3)
                col1.metric("Status", result.status)
                col2.metric("Time", f"{result.time_ms}ms" if result.time_ms else "N/A")
                col3.metric("Memory", f"{result.memory_kb}KB" if result.memory_kb else "N/A")

                st.markdown("**Input:**")
                st.code(r["input"], language="text")

                if expected:
                    st.markdown("**Expected:**")
                    st.code(expected, language="text")

                st.markdown("**Output (stdout):**")
                st.code(result.stdout or "(empty)", language="text")

                if result.stderr:
                    st.markdown("**Errors (stderr):**")
                    st.code(result.stderr, language="text")

                if result.compile_output:
                    st.markdown("**Compile Output:**")
                    st.code(result.compile_output, language="text")

                st.markdown(f"**Exit Code:** {result.exit_code}")

        if total > 1:
            st.markdown(f"**Summary: {passed}/{total} tests passed**")

# LLM Assistant sidebar
with col_llm:
    st.subheader("🤖 LLM Assistant")
    st.markdown("*Ask questions about your code*")

    # Model selection
    models = db.get_models()

    use_lmstudio_direct = st.checkbox(
        "LM Studio Direct",
        value=False,
        key="playground_lmstudio_direct",
    )

    llm_ready = False
    llm_config = None

    if use_lmstudio_direct:
        default_endpoint = config.get("llm", {}).get("providers", {}).get("lmstudio", {}).get("endpoint", "http://localhost:1234/v1")
        lmstudio_endpoint = st.text_input(
            "Endpoint",
            value=default_endpoint,
            key="playground_endpoint",
        )

        if lmstudio_endpoint:
            available_models = fetch_lmstudio_models(lmstudio_endpoint)
            if available_models:
                model_names = [m.get("id", "unknown") for m in available_models]
                selected_model = st.selectbox(
                    "Model",
                    options=model_names,
                    key="playground_model_select",
                )
                llm_config = LLMConfig(
                    provider="lmstudio",
                    endpoint=lmstudio_endpoint,
                    model_name=selected_model,
                )
                llm_ready = True
            else:
                st.warning("Could not fetch models")
    else:
        if models:
            model_options = {m["display_name"]: m for m in models}
            selected_model_name = st.selectbox(
                "Model",
                options=list(model_options.keys()),
                key="playground_configured_model",
            )
            model_info = model_options[selected_model_name]
            llm_config = LLMConfig(
                provider=model_info["provider"],
                endpoint=model_info["endpoint"],
                model_name=model_info["model_name"],
                api_key=model_info.get("api_key"),
                temperature=model_info.get("temperature", 0.7),
                max_tokens=model_info.get("max_tokens", 2048),
            )
            llm_ready = True
        else:
            st.info("No models configured. Enable LM Studio Direct or add a model in Settings.")

    st.markdown("---")

    # Quick action buttons
    st.markdown("**Quick Actions:**")

    col_q1, col_q2 = st.columns(2)

    with col_q1:
        explain_btn = st.button("📖 Explain", use_container_width=True, disabled=not llm_ready)
        fix_btn = st.button("🔧 Fix Errors", use_container_width=True, disabled=not llm_ready)

    with col_q2:
        optimize_btn = st.button("⚡ Optimize", use_container_width=True, disabled=not llm_ready)
        test_btn = st.button("🧪 Add Tests", use_container_width=True, disabled=not llm_ready)

    # Handle quick actions
    quick_action = None
    if explain_btn:
        quick_action = "Explain this code step by step. What does it do?"
    elif fix_btn:
        quick_action = "Find and fix any bugs or errors in this code. Show the corrected version."
    elif optimize_btn:
        quick_action = "Optimize this code for better performance or readability. Show the improved version."
    elif test_btn:
        quick_action = "Suggest additional test cases for this code, including edge cases."

    st.markdown("---")

    # Chat interface
    st.markdown("**Chat:**")

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history[-10:]:  # Show last 10 messages
            if msg["role"] == "user":
                st.markdown(f"**You:** {msg['content'][:200]}...")
            else:
                st.markdown(f"**Assistant:** {msg['content'][:500]}...")
            st.markdown("---")

    # User input
    user_question = st.text_area(
        "Ask about your code:",
        placeholder="e.g., Why is test 6 failing?",
        key="user_question",
        height=100,
    )

    # Use quick action or user question
    question_to_ask = quick_action or user_question

    if st.button("Send", type="primary", use_container_width=True, disabled=not llm_ready):
        if question_to_ask and st.session_state.playground_code:
            with st.spinner("Thinking..."):
                try:
                    llm = create_provider(llm_config)

                    # Build context
                    context = f"""Language: {st.session_state.playground_language}

Code:
```{st.session_state.playground_language}
{st.session_state.playground_code}
```"""

                    # Add output context if available
                    if st.session_state.playground_output:
                        context += "\n\nRecent test results:\n"
                        for i, r in enumerate(st.session_state.playground_output[:5]):
                            result = r["result"]
                            context += f"\nTest {i+1}:\n"
                            context += f"  Input: {r['input'][:100]}\n"
                            if r.get('expected'):
                                context += f"  Expected: {r['expected']}\n"
                            context += f"  Output: {result.stdout or '(empty)'}\n"
                            if result.stderr:
                                context += f"  Error: {result.stderr[:200]}\n"

                    prompt = f"""{context}

User question: {question_to_ask}

Please provide a helpful, concise answer."""

                    response = llm.generate(
                        prompt=prompt,
                        system_prompt="You are a helpful programming assistant. Provide clear, concise answers about code. When suggesting fixes, show the corrected code.",
                    )

                    # Add to chat history
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": question_to_ask,
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response.content,
                    })

                    st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")
        elif not st.session_state.playground_code:
            st.warning("Please enter some code first.")

    # Show latest response prominently
    if st.session_state.chat_history:
        latest = st.session_state.chat_history[-1]
        if latest["role"] == "assistant":
            st.markdown("---")
            st.markdown("**Latest Response:**")
            st.markdown(latest["content"])

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
