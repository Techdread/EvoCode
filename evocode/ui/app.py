"""
EvoCode - Main Streamlit Application

Run with: streamlit run ui/app.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import yaml

from storage import get_database
from core.challenges.loader import sync_challenges_to_db


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def init_app():
    """Initialize application state."""
    if "initialized" not in st.session_state:
        # Load config
        st.session_state.config = load_config()

        # Initialize database
        db = get_database()

        # Sync challenges from YAML files
        challenges_dir = Path(__file__).parent.parent / "challenges"
        if challenges_dir.exists():
            sync_challenges_to_db(challenges_dir, db)

        st.session_state.initialized = True


def main():
    """Main application entry point."""
    # Page config
    st.set_page_config(
        page_title="EvoCode",
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize
    init_app()

    # Main page content
    st.title("🧬 EvoCode")
    st.subheader("LLM Code Evaluation Framework")

    st.markdown("""
    Welcome to EvoCode! This framework allows you to:

    - **Evaluate LLMs** on coding challenges with automated test-driven feedback
    - **Compare models** to see which performs best on different problem types
    - **Track progress** with detailed metrics and visualizations

    ### Quick Start

    1. **Configure** your LLM endpoint in **Settings**
    2. **Browse** available challenges in **Challenges**
    3. **Run** an evaluation in **Run Evaluation**
    4. **Analyze** results in the **Dashboard**

    ### How It Works

    1. Select a challenge and LLM model
    2. The LLM generates code to solve the problem
    3. Judge0 executes the code against test cases
    4. If tests fail, feedback is provided and the LLM tries again
    5. This continues until all tests pass or max attempts reached

    ---
    Use the sidebar to navigate between pages.
    """)

    # Quick stats
    db = get_database()

    col1, col2, col3, col4 = st.columns(4)

    challenges = db.get_challenges()
    models = db.get_models()
    runs = db.get_runs(limit=1000)
    successful = [r for r in runs if r["status"] == "success"]

    with col1:
        st.metric("Challenges", len(challenges))

    with col2:
        st.metric("Models", len(models))

    with col3:
        st.metric("Total Runs", len(runs))

    with col4:
        pass_rate = (len(successful) / len(runs) * 100) if runs else 0
        st.metric("Pass Rate", f"{pass_rate:.1f}%")

    # Recent activity
    if runs:
        st.markdown("### Recent Runs")
        recent = db.get_recent_runs(limit=5)
        if recent:
            for run in recent:
                status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⚠️"
                st.markdown(
                    f"{status_emoji} **{run['challenge_name']}** with {run['model_name']} - "
                    f"Fitness: {run['best_fitness']:.0%}, Attempts: {run['attempts_used']}"
                )


if __name__ == "__main__":
    main()
