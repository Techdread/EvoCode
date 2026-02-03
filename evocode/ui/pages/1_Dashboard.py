"""Dashboard page - Overview metrics and charts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from storage import get_database


st.title("📊 Dashboard")

db = get_database()

# Summary metrics
st.subheader("Overview")

col1, col2, col3, col4 = st.columns(4)

challenges = db.get_challenges()
models = db.get_models()
runs = db.get_runs(limit=10000)
successful_runs = [r for r in runs if r["status"] == "success"]

with col1:
    st.metric("Total Challenges", len(challenges))

with col2:
    st.metric("Configured Models", len(models))

with col3:
    st.metric("Evaluation Runs", len(runs))

with col4:
    pass_rate = (len(successful_runs) / len(runs) * 100) if runs else 0
    st.metric("Overall Pass Rate", f"{pass_rate:.1f}%")

# Additional metrics row
col1, col2, col3, col4 = st.columns(4)

total_attempts = sum(r.get("attempts_used", 0) for r in runs)
total_tokens = sum((r.get("total_tokens_prompt", 0) or 0) + (r.get("total_tokens_completion", 0) or 0) for r in runs)

with col1:
    st.metric("Total Attempts", total_attempts)

with col2:
    avg_attempts = total_attempts / len(runs) if runs else 0
    st.metric("Avg Attempts/Run", f"{avg_attempts:.1f}")

with col3:
    st.metric("Total Tokens Used", f"{total_tokens:,}")

with col4:
    avg_fitness = sum(r.get("best_fitness", 0) for r in runs) / len(runs) if runs else 0
    st.metric("Avg Best Fitness", f"{avg_fitness:.1%}")

st.markdown("---")

# Charts section
if runs:
    st.subheader("Performance Analysis")

    # Model performance comparison
    model_perf = db.get_model_performance()

    if model_perf:
        st.markdown("### Model Performance")

        df_models = pd.DataFrame(model_perf)

        if not df_models.empty and "display_name" in df_models.columns:
            # Pass rate by model
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Pass Rate by Model**")
                chart_data = df_models[["display_name", "pass_rate"]].set_index("display_name")
                st.bar_chart(chart_data)

            with col2:
                st.markdown("**Average Attempts by Model**")
                chart_data = df_models[["display_name", "avg_attempts"]].set_index("display_name")
                st.bar_chart(chart_data)

    # Challenge statistics
    challenge_stats = db.get_challenge_stats()

    if challenge_stats:
        st.markdown("### Challenge Statistics")

        df_challenges = pd.DataFrame(challenge_stats)

        if not df_challenges.empty and "name" in df_challenges.columns:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Pass Rate by Challenge**")
                chart_data = df_challenges[["name", "pass_rate"]].dropna().set_index("name")
                if not chart_data.empty:
                    st.bar_chart(chart_data)

            with col2:
                st.markdown("**Difficulty Distribution**")
                if "difficulty" in df_challenges.columns:
                    difficulty_counts = df_challenges["difficulty"].value_counts()
                    st.bar_chart(difficulty_counts)

    # Recent activity timeline
    st.markdown("### Recent Activity")

    recent_runs = db.get_recent_runs(limit=20)

    if recent_runs:
        df_recent = pd.DataFrame(recent_runs)

        # Success rate over time (simple running average)
        df_recent["success"] = df_recent["status"].apply(lambda x: 1 if x == "success" else 0)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Recent Run Results**")
            status_counts = df_recent["status"].value_counts()
            st.bar_chart(status_counts)

        with col2:
            st.markdown("**Fitness Distribution**")
            fitness_data = df_recent["best_fitness"].dropna()
            if not fitness_data.empty:
                st.line_chart(fitness_data.values)

# Recent runs table
st.markdown("---")
st.subheader("Recent Evaluation Runs")

recent_runs = db.get_recent_runs(limit=15)

if recent_runs:
    # Format data for display
    table_data = []
    for run in recent_runs:
        status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⚠️"
        table_data.append({
            "Status": status_emoji,
            "Challenge": run["challenge_name"],
            "Model": run["model_name"],
            "Fitness": f"{run['best_fitness']:.0%}",
            "Attempts": f"{run['attempts_used']}/{run['max_attempts']}",
            "Tokens": run["total_tokens"] or 0,
            "Duration": f"{run['duration_seconds']:.1f}s" if run["duration_seconds"] else "N/A",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No evaluation runs yet. Go to 'Run Evaluation' to start!")

# Quick actions
st.markdown("---")
st.subheader("Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Run New Evaluation", use_container_width=True):
        st.switch_page("pages/2_Run_Evaluation.py")

with col2:
    if st.button("View Challenges", use_container_width=True):
        st.switch_page("pages/3_Challenges.py")

with col3:
    if st.button("Compare Models", use_container_width=True):
        st.switch_page("pages/4_Model_Comparison.py")
