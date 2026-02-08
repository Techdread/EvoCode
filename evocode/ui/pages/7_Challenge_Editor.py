"""Challenge Editor page - Create and edit challenges with LLM assistance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import yaml
import difflib
from typing import Optional

from storage import get_database
from core.llm import LLMConfig, create_provider
from core.judge import LANGUAGE_IDS
from ui.components import model_selector


# Supported languages for challenges
SUPPORTED_LANGUAGES = sorted([lang for lang in LANGUAGE_IDS.keys()])
DIFFICULTIES = ["easy", "medium", "hard"]


def load_challenge_yaml(challenge_id: str) -> Optional[dict]:
    """Load a challenge from its YAML file."""
    challenges_dir = Path(__file__).parent.parent.parent / "challenges"

    # Try to find the YAML file
    for yaml_file in challenges_dir.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if data and data.get("id") == challenge_id:
                    data["_file_path"] = str(yaml_file)
                    return data
        except Exception:
            continue
    return None


def save_challenge_yaml(challenge_data: dict, file_path: Optional[str] = None) -> str:
    """Save a challenge to a YAML file."""
    challenges_dir = Path(__file__).parent.parent.parent / "challenges"

    if file_path:
        path = Path(file_path)
    else:
        # Create new file based on challenge ID
        path = challenges_dir / f"{challenge_data['id']}.yaml"

    # Remove internal fields
    data = {k: v for k, v in challenge_data.items() if not k.startswith("_")}

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return str(path)


def generate_yaml_preview(challenge_data: dict) -> str:
    """Generate YAML string for preview."""
    data = {k: v for k, v in challenge_data.items() if not k.startswith("_")}
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def validate_challenge(challenge_data: dict) -> list[str]:
    """Validate challenge data and return list of errors."""
    errors = []

    if not challenge_data.get("id"):
        errors.append("Challenge ID is required")
    elif not challenge_data["id"].replace("_", "").replace("-", "").isalnum():
        errors.append("Challenge ID must be alphanumeric (underscores and hyphens allowed)")

    if not challenge_data.get("name"):
        errors.append("Challenge name is required")

    if not challenge_data.get("description"):
        errors.append("Description is required")

    if not challenge_data.get("language"):
        errors.append("Language is required")
    elif challenge_data["language"] not in SUPPORTED_LANGUAGES:
        errors.append(f"Language '{challenge_data['language']}' is not supported")

    if not challenge_data.get("runner"):
        errors.append("Runner code is required")
    elif "{{solution}}" not in challenge_data["runner"]:
        errors.append("Runner must contain {{solution}} placeholder")

    test_cases = challenge_data.get("test_cases", [])
    if not test_cases:
        errors.append("At least one visible test case is required")
    else:
        for i, tc in enumerate(test_cases):
            if not tc.get("input") and tc.get("input") != "":
                errors.append(f"Test case {i+1}: input is required")
            if not tc.get("expected") and tc.get("expected") != "":
                errors.append(f"Test case {i+1}: expected output is required")

    return errors


def sync_to_database(challenge_data: dict, db):
    """Sync challenge to database after saving YAML."""
    # Add/update challenge
    db.add_challenge(
        challenge_id=challenge_data["id"],
        name=challenge_data["name"],
        description=challenge_data["description"],
        language=challenge_data["language"],
        difficulty=challenge_data.get("difficulty", "medium"),
        runner=challenge_data["runner"],
        template=challenge_data.get("template"),
    )

    # Clear and re-add test cases
    db.clear_test_cases(challenge_data["id"])

    for tc in challenge_data.get("test_cases", []):
        db.add_test_case(
            challenge_id=challenge_data["id"],
            input_data=tc["input"],
            expected=tc["expected"],
            is_hidden=False,
        )

    for tc in challenge_data.get("hidden_tests", []):
        db.add_test_case(
            challenge_id=challenge_data["id"],
            input_data=tc["input"],
            expected=tc["expected"],
            is_hidden=True,
        )


# Page setup
st.title("✏️ Challenge Editor")

db = get_database()
models = db.get_models()
challenges = db.get_challenges()

# Sidebar for LLM assistance
with st.sidebar:
    st.header("🤖 LLM Assistant")

    # Use reusable model selector component
    llm_config, selected_model_id, use_server_defaults = model_selector(
        key_prefix="editor",
        show_configured=True,
        show_lmstudio=True,
        show_openrouter=True,
        db=db,
    )

    llm_ready = llm_config is not None

    if llm_ready:
        st.markdown("---")
        st.markdown("**Available Actions:**")
        st.markdown("- Generate test cases")
        st.markdown("- Improve description")
        st.markdown("- Suggest edge cases")
        st.markdown("- Generate sample solution")
        st.markdown("- Validate with LLM")
    else:
        st.info("Select a model source above to enable AI assistance.")

# Main content
col_select, col_new = st.columns([3, 1])

with col_select:
    challenge_options = {"-- Select a challenge --": None}
    challenge_options.update({c["name"]: c["id"] for c in challenges})

    selected_challenge_name = st.selectbox(
        "Edit Existing Challenge",
        options=list(challenge_options.keys()),
    )
    selected_challenge_id = challenge_options[selected_challenge_name]

with col_new:
    st.markdown("<br>", unsafe_allow_html=True)
    create_new = st.button("➕ Create New", use_container_width=True)

# Initialize session state for challenge data
if "editor_challenge" not in st.session_state:
    st.session_state.editor_challenge = None
if "editor_mode" not in st.session_state:
    st.session_state.editor_mode = None

# Handle selection/creation
if create_new:
    st.session_state.editor_mode = "create"
    st.session_state.editor_challenge = {
        "id": "",
        "name": "",
        "description": "",
        "language": "python",
        "difficulty": "medium",
        "template": "",
        "runner": "{{solution}}\n\n# Read input and call solution\n",
        "test_cases": [{"input": "", "expected": ""}],
        "hidden_tests": [],
    }
elif selected_challenge_id and selected_challenge_id != st.session_state.get("_last_selected"):
    st.session_state._last_selected = selected_challenge_id
    st.session_state.editor_mode = "edit"

    # Load from YAML
    yaml_data = load_challenge_yaml(selected_challenge_id)
    if yaml_data:
        st.session_state.editor_challenge = yaml_data
    else:
        # Fallback to database
        db_challenge = db.get_challenge(selected_challenge_id)
        test_cases = db.get_test_cases(selected_challenge_id)
        st.session_state.editor_challenge = {
            "id": db_challenge["id"],
            "name": db_challenge["name"],
            "description": db_challenge["description"],
            "language": db_challenge["language"],
            "difficulty": db_challenge["difficulty"],
            "template": db_challenge.get("template") or "",
            "runner": db_challenge["runner"],
            "test_cases": [{"input": tc["input"], "expected": tc["expected"]}
                          for tc in test_cases if not tc["is_hidden"]],
            "hidden_tests": [{"input": tc["input"], "expected": tc["expected"]}
                           for tc in test_cases if tc["is_hidden"]],
        }

# Editor form
if st.session_state.editor_challenge:
    challenge = st.session_state.editor_challenge

    st.markdown("---")
    mode_label = "Creating New Challenge" if st.session_state.editor_mode == "create" else f"Editing: {challenge.get('name', 'Untitled')}"
    st.subheader(mode_label)

    # Basic info
    col1, col2 = st.columns(2)

    with col1:
        challenge["id"] = st.text_input(
            "Challenge ID",
            value=challenge.get("id", ""),
            help="Unique identifier (e.g., 'two_sum', 'binary-search')",
            disabled=st.session_state.editor_mode == "edit",
        )
        challenge["name"] = st.text_input(
            "Name",
            value=challenge.get("name", ""),
            help="Display name for the challenge",
        )

    with col2:
        challenge["language"] = st.selectbox(
            "Language",
            options=SUPPORTED_LANGUAGES,
            index=SUPPORTED_LANGUAGES.index(challenge.get("language", "python")) if challenge.get("language") in SUPPORTED_LANGUAGES else 0,
        )
        challenge["difficulty"] = st.selectbox(
            "Difficulty",
            options=DIFFICULTIES,
            index=DIFFICULTIES.index(challenge.get("difficulty", "medium")) if challenge.get("difficulty") in DIFFICULTIES else 1,
        )

    # Description with LLM assist
    desc_col, assist_col = st.columns([4, 1])
    with desc_col:
        challenge["description"] = st.text_area(
            "Description",
            value=challenge.get("description", ""),
            height=200,
            help="Problem description shown to the LLM",
        )
    with assist_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ Improve", key="improve_desc", disabled=not llm_ready):
            if llm_config and challenge.get("description"):
                with st.spinner("Improving description..."):
                    try:
                        llm = create_provider(llm_config)

                        prompt = f"""Improve this coding challenge description to be clearer and more complete.
Keep the same problem but make it:
1. More precise about input/output format
2. Include clear examples
3. Mention edge cases to consider

Original description:
{challenge['description']}

Return ONLY the improved description, no other text."""

                        response = llm.generate(prompt, use_server_defaults=use_server_defaults)
                        st.session_state.editor_challenge["description"] = response.content
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # Template code
    challenge["template"] = st.text_area(
        "Template Code (optional)",
        value=challenge.get("template", ""),
        height=100,
        help="Starting code template shown to the LLM (function signature, etc.)",
    )

    # Runner code
    runner_col, runner_assist_col = st.columns([4, 1])
    with runner_col:
        challenge["runner"] = st.text_area(
            "Runner Code",
            value=challenge.get("runner", ""),
            height=150,
            help="Code that wraps the solution. Must contain {{solution}} placeholder.",
        )
    with runner_assist_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if "{{solution}}" not in challenge.get("runner", ""):
            st.warning("⚠️ Missing {{solution}}")

    # Test cases section
    st.markdown("---")
    st.subheader("Test Cases")

    test_tab, hidden_tab = st.tabs(["Visible Tests", "Hidden Tests"])

    with test_tab:
        st.markdown("*These tests are shown to the LLM as examples*")

        test_cases = challenge.get("test_cases", [])

        for i, tc in enumerate(test_cases):
            col1, col2, col3 = st.columns([5, 5, 1])
            with col1:
                test_cases[i]["input"] = st.text_area(
                    f"Input {i+1}",
                    value=tc.get("input", ""),
                    height=68,
                    key=f"visible_input_{i}",
                )
            with col2:
                test_cases[i]["expected"] = st.text_area(
                    f"Expected {i+1}",
                    value=tc.get("expected", ""),
                    height=68,
                    key=f"visible_expected_{i}",
                )
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_visible_{i}"):
                    test_cases.pop(i)
                    st.rerun()

        col_add, col_generate = st.columns(2)
        with col_add:
            if st.button("➕ Add Test Case", key="add_visible"):
                test_cases.append({"input": "", "expected": ""})
                st.rerun()
        with col_generate:
            if st.button("🤖 Generate Tests", key="gen_visible", disabled=not llm_ready):
                if llm_config and challenge.get("description"):
                    with st.spinner("Generating test cases..."):
                        try:
                            llm = create_provider(llm_config)

                            prompt = f"""Generate 3 test cases for this coding challenge.

Challenge: {challenge.get('name', 'Untitled')}
Language: {challenge.get('language', 'python')}
Description:
{challenge['description']}

Existing test cases:
{yaml.dump(test_cases, default_flow_style=False) if test_cases else 'None'}

Generate 3 NEW test cases (different from existing ones).
Format your response as YAML list:
- input: "input value"
  expected: "expected output"
- input: "another input"
  expected: "another output"

Return ONLY the YAML list, no other text."""

                            response = llm.generate(prompt, use_server_defaults=use_server_defaults)
                            # Parse response
                            try:
                                new_tests = yaml.safe_load(response.content)
                                if isinstance(new_tests, list):
                                    for t in new_tests:
                                        if isinstance(t, dict) and "input" in t and "expected" in t:
                                            test_cases.append({
                                                "input": str(t["input"]),
                                                "expected": str(t["expected"]),
                                            })
                                    st.rerun()
                            except:
                                st.error("Could not parse generated tests. Try again.")
                        except Exception as e:
                            st.error(f"Error: {e}")

        challenge["test_cases"] = test_cases

    with hidden_tab:
        st.markdown("*These tests are NOT shown to the LLM - used for final validation*")

        hidden_tests = challenge.get("hidden_tests", [])

        for i, tc in enumerate(hidden_tests):
            col1, col2, col3 = st.columns([5, 5, 1])
            with col1:
                hidden_tests[i]["input"] = st.text_area(
                    f"Input {i+1}",
                    value=tc.get("input", ""),
                    height=68,
                    key=f"hidden_input_{i}",
                )
            with col2:
                hidden_tests[i]["expected"] = st.text_area(
                    f"Expected {i+1}",
                    value=tc.get("expected", ""),
                    height=68,
                    key=f"hidden_expected_{i}",
                )
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_hidden_{i}"):
                    hidden_tests.pop(i)
                    st.rerun()

        col_add, col_generate = st.columns(2)
        with col_add:
            if st.button("➕ Add Hidden Test", key="add_hidden"):
                hidden_tests.append({"input": "", "expected": ""})
                st.rerun()
        with col_generate:
            if st.button("🤖 Generate Edge Cases", key="gen_hidden", disabled=not llm_ready):
                if llm_config and challenge.get("description"):
                    with st.spinner("Generating edge cases..."):
                        try:
                            llm = create_provider(llm_config)

                            prompt = f"""Generate 5 EDGE CASE test cases for this coding challenge.
Focus on tricky inputs that might break naive solutions:
- Empty inputs
- Single elements
- Maximum/minimum values
- Boundary conditions
- Special characters (if applicable)

Challenge: {challenge.get('name', 'Untitled')}
Language: {challenge.get('language', 'python')}
Description:
{challenge['description']}

Format your response as YAML list:
- input: "edge case input"
  expected: "expected output"

Return ONLY the YAML list, no other text."""

                            response = llm.generate(prompt, use_server_defaults=use_server_defaults)
                            try:
                                new_tests = yaml.safe_load(response.content)
                                if isinstance(new_tests, list):
                                    for t in new_tests:
                                        if isinstance(t, dict) and "input" in t and "expected" in t:
                                            hidden_tests.append({
                                                "input": str(t["input"]),
                                                "expected": str(t["expected"]),
                                            })
                                    st.rerun()
                            except:
                                st.error("Could not parse generated tests. Try again.")
                        except Exception as e:
                            st.error(f"Error: {e}")

        challenge["hidden_tests"] = hidden_tests

    # Actions section
    st.markdown("---")
    st.subheader("Actions")

    col_validate, col_preview, col_solution, col_save = st.columns(4)

    with col_validate:
        if st.button("✅ Validate", use_container_width=True):
            errors = validate_challenge(challenge)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                st.success("Challenge is valid!")

    with col_preview:
        if st.button("👁️ Preview YAML", use_container_width=True):
            st.session_state.show_preview = True

    with col_solution:
        if st.button("🧪 Gen Solution", use_container_width=True, disabled=not llm_ready):
            if llm_config and challenge.get("description"):
                with st.spinner("Generating sample solution..."):
                    try:
                        llm = create_provider(llm_config)

                        prompt = f"""Write a solution for this coding challenge.

Challenge: {challenge.get('name', 'Untitled')}
Language: {challenge.get('language', 'python')}
Description:
{challenge['description']}

Template:
{challenge.get('template', 'No template provided')}

Return ONLY the solution code, no explanations."""

                        response = llm.generate(prompt, use_server_defaults=use_server_defaults)
                        st.session_state.generated_solution = response.content
                    except Exception as e:
                        st.error(f"Error: {e}")

    with col_save:
        if st.button("💾 Save", type="primary", use_container_width=True):
            errors = validate_challenge(challenge)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    file_path = challenge.get("_file_path")
                    saved_path = save_challenge_yaml(challenge, file_path)
                    sync_to_database(challenge, db)
                    st.success(f"Saved to {saved_path}")
                    st.session_state.editor_mode = "edit"
                    st.session_state._last_selected = challenge["id"]
                except Exception as e:
                    st.error(f"Error saving: {e}")

    # Preview modal
    if st.session_state.get("show_preview"):
        st.markdown("---")
        st.subheader("YAML Preview")

        yaml_content = generate_yaml_preview(challenge)

        # Show diff if editing existing
        if st.session_state.editor_mode == "edit" and challenge.get("_file_path"):
            try:
                with open(challenge["_file_path"]) as f:
                    original = f.read()

                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    yaml_content.splitlines(keepends=True),
                    fromfile="Original",
                    tofile="Modified",
                )
                diff_text = "".join(diff)
                if diff_text:
                    st.markdown("**Changes:**")
                    st.code(diff_text, language="diff")
                else:
                    st.info("No changes from original file.")
            except:
                pass

        st.code(yaml_content, language="yaml")

        if st.button("Close Preview"):
            st.session_state.show_preview = False
            st.rerun()

    # Show generated solution
    if st.session_state.get("generated_solution"):
        st.markdown("---")
        st.subheader("Generated Sample Solution")
        st.code(st.session_state.generated_solution, language=challenge.get("language", "python"))

        if st.button("Clear Solution"):
            del st.session_state.generated_solution
            st.rerun()

else:
    st.info("Select a challenge to edit or click 'Create New' to start a new challenge.")
