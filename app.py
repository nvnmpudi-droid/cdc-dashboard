"""
OSIS – Epistemic Dashboard (v2.1)
===================================
Reads from:
  - osis_strategic_archives.db  (canonical_metrics table)
  - logic_output.json           (LogicAgent Fact Packet)
  - strategic_brief.txt         (Inference Agent brief)
  - forecast_output.json        (Prophet 4-week ahead forecast)

Run:  streamlit run app.py
"""

import json
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

DB_NAME          = "osis_strategic_archives.db"
LOGIC_OUTPUT     = "logic_output.json"
BRIEF_OUTPUT     = "strategic_brief.txt"
FORECAST_OUTPUT  = "forecast_output.json"

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
        return json.load(f)


@st.cache_data(ttl=60)
def load_forecast():
    if not Path(FORECAST_OUTPUT).exists():
        return None
    with open(FORECAST_OUTPUT) as f:
        return json.load(f)


# ── Load everything ───────────────────────────────────────────────────────────
df_all      = load_canonical_metrics()
logic_out   = load_logic_output()
brief_data  = load_brief()
forecast    = load_forecast()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    if df_all.empty:
        st.error("No data. Run:  python main.py")
    else:
        states = sorted(df_all["state"].unique().tolist())
        selected_state = st.selectbox(
            "Jurisdiction", states,
            index=states.index("United States") if "United States" in states else 0
        )
        st.markdown("---")
        st.markdown("**Pipeline Status**")
        st.markdown("✅ DB" if Path(DB_NAME).exists() else "❌ DB not found")
        st.markdown("✅ Logic Agent" if Path(LOGIC_OUTPUT).exists() else "⚠️ logic_output.json missing")
        st.markdown("✅ Inference Agent" if Path(BRIEF_OUTPUT).exists() else "⚠️ strategic_brief.txt missing")
        st.markdown("✅ Forecast Agent" if Path(FORECAST_OUTPUT).exists() else "⚠️ forecast_output.json missing")
        st.markdown("---")
        st.caption("OSIS v2.1 | CDC NVSS 2020–2023")

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
    col4.metric("Latest Z-Score", f"{z_score:.2f}", delta=severity,
                delta_color="inverse" if z_score < 0 else "normal")
else:
    col4.metric("Z-Score", "Run main.py")

st.markdown("---")

# ── Chart Row 1: History + Forecast ──────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Weekly Deaths + 4-Week Forecast")

    fig = go.Figure()

    # Historical line
    fig.add_trace(go.Scatter(
        x=df["time_period"], y=df["metric_value"],
        mode="lines", name="Observed",
        line=dict(color="#e63946", width=2)
    ))

    # Anomaly markers
    if logic_out and logic_out.get("status") == "success":
        top_anomalies = logic_out["payload"].get("top_anomalies", [])
        if top_anomalies:
            anom_df = pd.DataFrame(top_anomalies)
            anom_df["date"] = pd.to_datetime(anom_df["date"])
            fig.add_trace(go.Scatter(
                x=anom_df["date"], y=anom_df["value"],
                mode="markers", name="Anomaly (≥2σ)",
                marker=dict(color="orange", size=10, symbol="x")
            ))

    # Forecast traces
    if forecast and forecast.get("status") == "success":
        fcast_df = pd.DataFrame(forecast["forecast"])
        fcast_df["week_ending"] = pd.to_datetime(fcast_df["week_ending"])

        # Uncertainty band
        fig.add_trace(go.Scatter(
            x=pd.concat([fcast_df["week_ending"], fcast_df["week_ending"][::-1]]),
            y=pd.concat([fcast_df["upper_95"], fcast_df["lower_95"][::-1]]),
            fill="toself", fillcolor="rgba(99,110,250,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% Interval", showlegend=True
        ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=fcast_df["week_ending"], y=fcast_df["forecast"],
            mode="lines+markers", name="Forecast (Prophet)",
            line=dict(color="#636efa", width=2, dash="dash"),
            marker=dict(size=8)
        ))

    fig.update_layout(
        showlegend=True, plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117", font_color="#e0e0e0",
        legend=dict(bgcolor="#1e1e2e"),
        xaxis_title="Week", yaxis_title="Deaths"
    )
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
    fig2.update_layout(
        showlegend=False, plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117", font_color="#e0e0e0"
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Forecast Detail Panel ─────────────────────────────────────────────────────
st.subheader("🔮 Forecast Agent — Prophet 4-Week Ahead")

if forecast and forecast.get("status") == "success":
    trend = forecast["trend"]
    last  = forecast["last_known"]

    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Last Known Value", f"{last['value']:,}", delta=last["date"])
    fc2.metric("Trend Direction", trend["direction"].capitalize())
    fc3.metric("4-Week Change", f"{trend['pct_change']:+.1f}%")
    fc4.metric("Forecast Start", f"{trend['start_value']:,}")

    fcast_df = pd.DataFrame(forecast["forecast"])
    fcast_df.columns = ["Week Ending", "Forecast", "Lower 95%", "Upper 95%"]
    fcast_df["Forecast"]  = fcast_df["Forecast"].apply(lambda x: f"{x:,}")
    fcast_df["Lower 95%"] = fcast_df["Lower 95%"].apply(lambda x: f"{x:,}")
    fcast_df["Upper 95%"] = fcast_df["Upper 95%"].apply(lambda x: f"{x:,}")
    st.dataframe(fcast_df, use_container_width=True, hide_index=True)

    st.caption(f"⚠️ {forecast['tarka_note']}")
else:
    st.info("Run `python main.py` to generate forecast.")

st.markdown("---")

# ── Logic Agent Panel ─────────────────────────────────────────────────────────
st.subheader("🧠 Logic Agent — Anomaly Audit")

if logic_out and logic_out.get("status") == "success":
    p = logic_out["payload"]
    a = p["analysis"]
    b = p["baseline_stats"]

    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.metric("Observed Value",   f"{p['observed_value']:,.0f}")
    lc2.metric("4-Week Baseline",  f"{b['rolling_mean']:,.0f}")
    lc3.metric("Z-Score",          f"{a['z_score']:.4f}")
    lc4.metric("Severity",         a["severity"])

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
st.subheader("🏛️ Governed Strategic Brief")

if brief_data:
    tarka      = brief_data.get("tarka_validation", {})
    passed     = tarka.get("passed", False)
    issues     = tarka.get("issues", [])
    brief_text = brief_data.get("brief", "")
    gen_time   = brief_data.get("generated_at", "")[:19].replace("T", " ")
    model      = brief_data.get("model", "unknown")
    confidence = brief_data.get("confidence", 0.0)
    badge      = tarka.get("badge", "")

    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("Tarka Validation", badge)
    bc2.metric("Model", model)
    bc3.metric("Confidence", f"{confidence:.2f}" if confidence else "—")

    if not passed:
        for issue in issues:
            st.warning(issue)

    st.markdown(f"*Generated: {gen_time} UTC*")
    st.markdown(f"<div class='brief-box'>{brief_text}</div>", unsafe_allow_html=True)

    with st.expander("📄 Full Brief JSON"):
        st.json(brief_data)
else:
    st.info(
        "Strategic Brief not yet generated. "
        "Start Ollama (`ollama serve`) then run `python main.py --skip-db`."
    )
    if logic_out and logic_out.get("status") == "success":
        a = logic_out["payload"]["analysis"]
        z = a["z_score"]
        st.markdown("**Deterministic Fallback:**")
        if z < -2.0:
            st.warning(
                f"Z-Score of {z:.2f} is strongly negative — likely CDC reporting lag. "
                "Validate the pipeline before acting on this figure."
            )
        elif z > 2.0:
            st.error(
                f"Z-Score of {z:.2f} signals excess mortality ({abs(z):.1f}σ above baseline). "
                "Escalate to epidemiological review."
            )
        else:
            st.success("System operating within normal parameters.")

st.markdown("---")
st.caption("OSIS v2.1 — Neuro-Symbolic Public Health Intelligence | CDC NVSS 2020–2023")