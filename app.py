"""
OSIS – Epistemic Dashboard (v2.0)
===================================
Reads from:
  - osis_strategic_archives.db  (canonical_metrics table)
  - logic_output.json           (LogicAgent Fact Packet)
  - strategic_brief.txt         (TinyLlama brief, optional)

Run:  streamlit run app.py
"""

import json
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

DB_NAME          = "osis_strategic_archives.db"
LOGIC_OUTPUT     = "logic_output.json"
BRIEF_OUTPUT     = "strategic_brief.txt"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OSIS — Epistemic Dashboard",
    page_icon="🏛️",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card { background:#1e1e2e; border-radius:8px; padding:16px; }
    .severity-CRITICAL { color:#ff4b4b; font-weight:bold; }
    .severity-WARNING  { color:#ffa500; font-weight:bold; }
    .severity-NORMAL   { color:#21c354; font-weight:bold; }
    .brief-box {
        background:#0e1117; border:1px solid #333; border-radius:8px;
        padding:20px; font-size:15px; line-height:1.7; color:#e0e0e0;
    }
    .tarka-pass { color:#21c354; }
    .tarka-fail { color:#ff4b4b; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏛️ OSIS — Organizational Strategy Intelligence System")
st.caption("Neuro-Symbolic Epistemic Dashboard  |  CDC Mortality Surveillance")
st.markdown("---")


# ── Data Loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_canonical_metrics():
    if not Path(DB_NAME).exists():
        return pd.DataFrame()
    con = duckdb.connect(DB_NAME, read_only=True)
    df = con.execute("""
        SELECT time_period, metric_value, state, metric_name
        FROM canonical_metrics
        WHERE metric_name = 'weekly_deaths_all_cause'
        ORDER BY time_period
    """).df()
    con.close()
    df["time_period"] = pd.to_datetime(df["time_period"])
    return df


@st.cache_data(ttl=60)
def load_logic_output():
    if not Path(LOGIC_OUTPUT).exists():
        return None
    with open(LOGIC_OUTPUT) as f:
        return json.load(f)


@st.cache_data(ttl=60)
def load_brief():
    if not Path(BRIEF_OUTPUT).exists():
        return None
    with open(BRIEF_OUTPUT) as f:
        data = json.load(f)
    return data


# ── Load everything ───────────────────────────────────────────────────────────
df_all     = load_canonical_metrics()
logic_out  = load_logic_output()
brief_data = load_brief()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    if df_all.empty:
        st.error("No data. Run:  python main.py --skip-db")
    else:
        states = sorted(df_all["state"].unique().tolist())
        selected_state = st.selectbox("Jurisdiction", states,
                                      index=states.index("United States")
                                      if "United States" in states else 0)
        st.markdown("---")
        st.markdown("**Pipeline Status**")
        st.markdown("✅ DB: `osis_strategic_archives.db`" if Path(DB_NAME).exists()
                    else "❌ DB not found")
        st.markdown("✅ `logic_output.json`" if Path(LOGIC_OUTPUT).exists()
                    else "⚠️ Run `python main.py --skip-db`")
        st.markdown("✅ `strategic_brief.txt`" if Path(BRIEF_OUTPUT).exists()
                    else "⚠️ Ollama not run yet")
        st.markdown("---")
        st.caption("OSIS v1.0 | CDC NVSS 2020–2023")

if df_all.empty:
    st.warning("Run `python main.py` first to initialize the OSIS archive.")
    st.stop()

df = df_all[df_all["state"] == selected_state].copy()

# ── KPI Row ───────────────────────────────────────────────────────────────────
st.subheader("📊 Key Metrics")

col1, col2, col3, col4 = st.columns(4)

total    = int(df["metric_value"].sum())
peak_idx = df["metric_value"].idxmax()
peak_val = int(df.loc[peak_idx, "metric_value"])
peak_dt  = df.loc[peak_idx, "time_period"].strftime("%Y-%m-%d")
latest   = df.iloc[-1]

# Pull Z-score from logic output if available
z_score  = None
severity = "N/A"
if logic_out and logic_out.get("status") == "success":
    p = logic_out["payload"]
    if p.get("state") == selected_state:
        z_score  = p["analysis"]["z_score"]
        severity = p["analysis"]["severity"]

col1.metric("Total Deaths (Period)", f"{total:,}")
col2.metric("Peak Week", peak_dt)
col3.metric("Peak Value", f"{peak_val:,}")

if z_score is not None:
    sev_color = {"CRITICAL": "🔴", "WARNING": "🟡", "NORMAL": "🟢"}.get(severity, "⚪")
    col4.metric("Latest Z-Score", f"{z_score:.2f}", delta=severity,
                delta_color="inverse" if z_score < 0 else "normal")
else:
    col4.metric("Z-Score", "Run analysis.py")

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Weekly All-Cause Deaths")
    fig = px.line(
        df, x="time_period", y="metric_value",
        labels={"time_period": "Week", "metric_value": "Deaths"},
        color_discrete_sequence=["#e63946"]
    )
    # Overlay anomaly markers if logic output available
    if logic_out and logic_out.get("status") == "success":
        top_anomalies = logic_out["payload"].get("top_anomalies", [])
        if top_anomalies:
            anom_df = pd.DataFrame(top_anomalies)
            anom_df["date"] = pd.to_datetime(anom_df["date"])
            fig.add_scatter(
                x=anom_df["date"], y=anom_df["value"],
                mode="markers",
                marker=dict(color="orange", size=10, symbol="x"),
                name="Anomaly (≥2σ)"
            )
    fig.update_layout(showlegend=True, plot_bgcolor="#0e1117",
                      paper_bgcolor="#0e1117", font_color="#e0e0e0")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📉 Annual Aggregation")
    df["year"] = df["time_period"].dt.year
    annual = df.groupby("year")["metric_value"].sum().reset_index()
    fig2 = px.bar(
        annual, x="year", y="metric_value",
        labels={"year": "Year", "metric_value": "Total Deaths"},
        color="metric_value", color_continuous_scale="Reds",
        text_auto=True
    )
    fig2.update_layout(showlegend=False, plot_bgcolor="#0e1117",
                       paper_bgcolor="#0e1117", font_color="#e0e0e0")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Logic Agent Panel ─────────────────────────────────────────────────────────
st.subheader("🧠 Logic Agent — Fact Packet")

if logic_out and logic_out.get("status") == "success":
    p = logic_out["payload"]
    a = p["analysis"]
    b = p["baseline_stats"]

    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.metric("Observed Value",  f"{p['observed_value']:,.0f}")
    lc2.metric("4-Week Baseline", f"{b['rolling_mean']:,.0f}")
    lc3.metric("Z-Score",         f"{a['z_score']:.4f}")
    lc4.metric("Severity",        a["severity"])

    # Z-score gauge
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=a["z_score"],
        title={"text": "Z-Score (Latest Week)"},
        gauge={
            "axis": {"range": [-6, 6]},
            "bar": {"color": "#e63946"},
            "steps": [
                {"range": [-6, -2], "color": "#ff4b4b"},
                {"range": [-2,  2], "color": "#21c354"},
                {"range": [ 2,  6], "color": "#ff4b4b"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": a["z_score"]
            }
        }
    ))
    fig_gauge.update_layout(
        height=250, paper_bgcolor="#0e1117", font_color="#e0e0e0"
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    with st.expander("📄 Full Fact Packet JSON"):
        st.json(logic_out)
else:
    st.info("Run `python main.py --skip-db` to generate the Fact Packet.")

st.markdown("---")

# ── Strategic Brief Panel ─────────────────────────────────────────────────────
st.subheader("🏛️ Governed Strategic Brief (TinyLlama)")

if brief_data:
    validation = brief_data.get("validation", {})
    passed     = validation.get("passed", False)
    issues     = validation.get("issues", [])
    brief_text = brief_data.get("brief", "")
    gen_time   = brief_data.get("generated_at", "")[:19].replace("T", " ")

    # Tarka validation badge
    if passed:
        st.markdown("**Tarka Validation:** <span class='tarka-pass'>✅ PASSED</span>",
                    unsafe_allow_html=True)
    else:
        st.markdown("**Tarka Validation:** <span class='tarka-fail'>⚠️ ISSUES DETECTED</span>",
                    unsafe_allow_html=True)
        for issue in issues:
            st.warning(issue)

    st.markdown(f"*Generated: {gen_time} UTC | Model: {brief_data.get('model', 'tinyllama')}*")
    st.markdown(f"<div class='brief-box'>{brief_text}</div>", unsafe_allow_html=True)

else:
    st.info(
        "Strategic Brief not yet generated.\n\n"
        "**To enable:**\n"
        "1. `ollama serve` (in a separate terminal)\n"
        "2. `ollama pull tinyllama`\n"
        "3. `python main.py --skip-db`"
    )
    # Show deterministic fallback if logic output exists
    if logic_out and logic_out.get("status") == "success":
        a = logic_out["payload"]["analysis"]
        z = a["z_score"]
        st.markdown("**Deterministic Interpretation (No-LLM Fallback):**")
        if z < -2.0:
            st.warning(
                f"Z-Score of {z:.2f} is strongly negative. "
                "In CDC surveillance this typically indicates **reporting lag** — "
                "death certificates have not yet been fully processed. "
                "Validate the reporting pipeline before acting on this figure."
            )
        elif z > 2.0:
            st.error(
                f"Z-Score of {z:.2f} signals **excess mortality**. "
                f"Observed deaths exceed the 4-week baseline by {abs(z):.1f}σ. "
                "Escalate to epidemiological review."
            )
        else:
            st.success("System operating within normal parameters.")

st.markdown("---")
st.caption("OSIS v1.0 | Data: CDC NVSS | Epistemic Framework: Nyāya/Tarka")