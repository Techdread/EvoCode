"""Model Comparison page - Compare LLM performance side-by-side."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from storage import get_database


st.title("🔍 Model Comparison")

db = get_database()

# Get models and performance data
models = db.get_models()
model_perf = db.get_model_performance()

if not models:
    st.warning("No models configured. Please add models in Settings.")
    st.stop()

if not model_perf or not any(p.get("total_runs", 0) for p in model_perf):
    st.info("No evaluation data yet. Run some evaluations first!")
    st.stop()

# Overview comparison
st.subheader("Performance Overview")

# Create DataFrame
df = pd.DataFrame(model_perf)

# Filter to models with runs
df = df[df["total_runs"] > 0]

if df.empty:
    st.info("No models have been evaluated yet.")
    st.stop()

# Summary table
summary_cols = [
    "display_name",
    "total_runs",
    "successful_runs",
    "pass_rate",
    "avg_fitness",
    "avg_attempts",
    "total_tokens_prompt",
    "total_tokens_completion",
]

available_cols = [c for c in summary_cols if c in df.columns]
summary_df = df[available_cols].copy()

# Rename for display
summary_df = summary_df.rename(columns={
    "display_name": "Model",
    "total_runs": "Runs",
    "successful_runs": "Solved",
    "pass_rate": "Pass Rate %",
    "avg_fitness": "Avg Fitness",
    "avg_attempts": "Avg Attempts",
    "total_tokens_prompt": "Prompt Tokens",
    "total_tokens_completion": "Completion Tokens",
})

st.dataframe(summary_df, use_container_width=True, hide_index=True)

# Charts
st.markdown("---")
st.subheader("Visual Comparison")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Pass Rate by Model**")
    if "pass_rate" in df.columns and "display_name" in df.columns:
        chart_df = df[["display_name", "pass_rate"]].set_index("display_name")
        st.bar_chart(chart_df)

with col2:
    st.markdown("**Average Attempts to Solve**")
    if "avg_attempts" in df.columns and "display_name" in df.columns:
        chart_df = df[["display_name", "avg_attempts"]].set_index("display_name")
        st.bar_chart(chart_df)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Total Runs by Model**")
    if "total_runs" in df.columns and "display_name" in df.columns:
        chart_df = df[["display_name", "total_runs"]].set_index("display_name")
        st.bar_chart(chart_df)

with col2:
    st.markdown("**Token Usage (Total)**")
    if all(c in df.columns for c in ["display_name", "total_tokens_prompt", "total_tokens_completion"]):
        df["total_tokens"] = df["total_tokens_prompt"] + df["total_tokens_completion"]
        chart_df = df[["display_name", "total_tokens"]].set_index("display_name")
        st.bar_chart(chart_df)

# Per-challenge comparison
st.markdown("---")
st.subheader("Per-Challenge Comparison")

# Get all challenges with runs
challenge_stats = db.get_challenge_stats()
challenges_with_runs = [c for c in challenge_stats if c.get("total_runs", 0) > 0]

if challenges_with_runs:
    challenge_names = {c["challenge_id"]: c["name"] for c in challenges_with_runs}

    selected_challenge = st.selectbox(
        "Select Challenge",
        options=list(challenge_names.keys()),
        format_func=lambda x: challenge_names.get(x, x),
    )

    if selected_challenge:
        # Get runs for this challenge grouped by model
        runs = db.get_runs(challenge_id=selected_challenge, limit=1000)

        if runs:
            # Group by model
            model_results = {}
            for run in runs:
                model_id = run["model_id"]
                if model_id not in model_results:
                    model_results[model_id] = {
                        "runs": 0,
                        "successful": 0,
                        "total_fitness": 0,
                        "total_attempts": 0,
                        "total_tokens": 0,
                    }
                model_results[model_id]["runs"] += 1
                if run["status"] == "success":
                    model_results[model_id]["successful"] += 1
                model_results[model_id]["total_fitness"] += run.get("best_fitness", 0)
                model_results[model_id]["total_attempts"] += run.get("attempts_used", 0)
                model_results[model_id]["total_tokens"] += (
                    (run.get("total_tokens_prompt", 0) or 0) +
                    (run.get("total_tokens_completion", 0) or 0)
                )

            # Build comparison table
            comparison_data = []
            for model_id, stats in model_results.items():
                model = db.get_model(model_id)
                if model:
                    comparison_data.append({
                        "Model": model["display_name"],
                        "Runs": stats["runs"],
                        "Solved": stats["successful"],
                        "Pass Rate": f"{stats['successful'] / stats['runs'] * 100:.0f}%",
                        "Avg Fitness": f"{stats['total_fitness'] / stats['runs']:.2f}",
                        "Avg Attempts": f"{stats['total_attempts'] / stats['runs']:.1f}",
                        "Avg Tokens": f"{stats['total_tokens'] / stats['runs']:.0f}",
                    })

            if comparison_data:
                st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)

                # Visual comparison for this challenge
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"**Pass Rate on {challenge_names.get(selected_challenge, selected_challenge)}**")
                    chart_data = {d["Model"]: int(d["Pass Rate"].replace("%", "")) for d in comparison_data}
                    st.bar_chart(chart_data)

                with col2:
                    st.markdown("**Average Attempts**")
                    chart_data = {d["Model"]: float(d["Avg Attempts"]) for d in comparison_data}
                    st.bar_chart(chart_data)
else:
    st.info("No challenges have been evaluated yet.")

# Head-to-head comparison
st.markdown("---")
st.subheader("Head-to-Head Comparison")

if len(models) >= 2:
    col1, col2 = st.columns(2)

    model_options = {m["display_name"]: m["id"] for m in models}

    with col1:
        model1_name = st.selectbox("Model 1", list(model_options.keys()), key="m1")
        model1_id = model_options[model1_name]

    with col2:
        model2_name = st.selectbox(
            "Model 2",
            [m for m in model_options.keys() if m != model1_name],
            key="m2"
        )
        model2_id = model_options[model2_name]

    # Get performance for both models
    perf1 = next((p for p in model_perf if p.get("model_id") == model1_id), {})
    perf2 = next((p for p in model_perf if p.get("model_id") == model2_id), {})

    if perf1.get("total_runs") and perf2.get("total_runs"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### {model1_name}")
            st.metric("Total Runs", perf1.get("total_runs", 0))
            st.metric("Pass Rate", f"{perf1.get('pass_rate', 0):.1f}%")
            st.metric("Avg Fitness", f"{perf1.get('avg_fitness', 0):.2f}")
            st.metric("Avg Attempts", f"{perf1.get('avg_attempts', 0):.1f}")
            total_tokens1 = (perf1.get("total_tokens_prompt", 0) or 0) + (perf1.get("total_tokens_completion", 0) or 0)
            st.metric("Total Tokens", f"{total_tokens1:,}")

        with col2:
            st.markdown(f"### {model2_name}")
            st.metric("Total Runs", perf2.get("total_runs", 0))

            # Show delta
            pr1, pr2 = perf1.get("pass_rate", 0), perf2.get("pass_rate", 0)
            st.metric("Pass Rate", f"{pr2:.1f}%", delta=f"{pr2 - pr1:.1f}%")

            af1, af2 = perf1.get("avg_fitness", 0), perf2.get("avg_fitness", 0)
            st.metric("Avg Fitness", f"{af2:.2f}", delta=f"{af2 - af1:.2f}")

            aa1, aa2 = perf1.get("avg_attempts", 0), perf2.get("avg_attempts", 0)
            st.metric("Avg Attempts", f"{aa2:.1f}", delta=f"{aa2 - aa1:.1f}", delta_color="inverse")

            total_tokens2 = (perf2.get("total_tokens_prompt", 0) or 0) + (perf2.get("total_tokens_completion", 0) or 0)
            st.metric("Total Tokens", f"{total_tokens2:,}")

        # Winner summary
        st.markdown("---")
        wins = {"model1": 0, "model2": 0}

        if pr1 > pr2:
            wins["model1"] += 1
        elif pr2 > pr1:
            wins["model2"] += 1

        if af1 > af2:
            wins["model1"] += 1
        elif af2 > af1:
            wins["model2"] += 1

        # Lower attempts is better
        if aa1 < aa2:
            wins["model1"] += 1
        elif aa2 < aa1:
            wins["model2"] += 1

        if wins["model1"] > wins["model2"]:
            st.success(f"**{model1_name}** performs better overall")
        elif wins["model2"] > wins["model1"]:
            st.success(f"**{model2_name}** performs better overall")
        else:
            st.info("Both models perform similarly")

    else:
        st.info("Both models need evaluation data for comparison.")
else:
    st.info("Add at least 2 models to enable head-to-head comparison.")
