import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from data_ingest import fetch_cdc_data
from processing import filter_recent_years
from analysis import summarize_covid_deaths
from summarization import ai_narrative_summary

st.set_page_config(
    page_title="Public Health AI Dashboard",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Public Health AI Dashboard")
st.caption("Powered by CDC open data")

# ── Sidebar controls ──────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    start_year = st.slider("Start Year", 2020, 2023, 2020)
    st.markdown("---")
    st.info("Data source: CDC National Vital Statistics System")

# ── Load data ─────────────────────────────────────────
with st.spinner("Loading CDC data..."):
    df = fetch_cdc_data()
    df_filtered = filter_recent_years(df, year=start_year)
    summary = summarize_covid_deaths(df_filtered)
    narrative = ai_narrative_summary(summary)

# ── KPI cards ─────────────────────────────────────────
st.subheader("📊 Key Metrics")
col1, col2, col3 = st.columns(3)

total_deaths = int(summary['COVID-19 Deaths'].sum())
peak_year = int(summary.loc[summary['COVID-19 Deaths'].idxmax(), 'Year'])
peak_deaths = int(summary['COVID-19 Deaths'].max())

col1.metric("Total Deaths", f"{total_deaths:,}")
col2.metric("Peak Year", str(peak_year))
col3.metric("Peak Year Deaths", f"{peak_deaths:,}")

st.markdown("---")

# ── Charts ────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Deaths by Year")
    fig = px.bar(
        summary,
        x='Year',
        y='COVID-19 Deaths',
        color='COVID-19 Deaths',
        color_continuous_scale='Reds',
        text_auto=True
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📉 Trend Over Time")
    fig2 = px.line(
        summary,
        x='Year',
        y='COVID-19 Deaths',
        markers=True,
        line_shape='spline'
    )
    fig2.update_traces(line_color='#e63946', marker_size=10)
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── AI Summary ────────────────────────────────────────
st.subheader("🤖 AI Narrative Summary (Epistemic Audit)")

# Parse the narrative to separate the Story from the Validation
if "[VALIDATION STATUS:" in narrative:
    story_part, validation_part = narrative.split("[VALIDATION STATUS:", 1)
    validation_status = validation_part.replace("]", "").strip()
else:
    story_part = narrative
    validation_status = "UNKNOWN"

# Display the Story
st.write(story_part)

# Display the Audit Badge
if "VALIDATED" in validation_status and "CONTRADICTION" not in validation_status:
    st.success(f"✅ AUDIT PASSED: {validation_status}")
elif "CONTRADICTION" in validation_status:
    st.error(f"❌ AUDIT FAILED: {validation_status}")
else:
    st.warning(f"⚠️ AUDIT UNCERTAIN: {validation_status}")

# ── Raw data ──────────────────────────────────────────
with st.expander("📄 View Raw Data"):
    st.dataframe(summary, use_container_width=True)
