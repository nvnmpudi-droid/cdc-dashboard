import streamlit as st
import pandas as pd
from data_ingest import fetch_cdc_data
from processing import filter_recent_years
from analysis import summarize_covid_deaths
from dashboard import plot_covid_deaths
from summarization import ai_narrative_summary

st.title("CDC COVID-19 Mortality Dashboard")

# Data Loading
if st.button("Load CDC Data"):
    df = fetch_cdc_data()
    st.write("Columns available:", df.columns.tolist())
    st.write(df.head())

    df_filtered = filter_recent_years(df)
    summary = summarize_covid_deaths(df_filtered)
    st.subheader("Yearly COVID Mortality Summary")
    st.write(summary)

    st.subheader("Trend Plot")
    st.pyplot(plot_covid_deaths(summary))

    ai_summary = ai_narrative_summary(summary)
    st.subheader("AI Summary")
    st.write(ai_summary)

st.markdown("---")
query = st.text_input("Ask a COVID mortality dashboard question:")
if query:
    keywords = ['covid', 'death', 'mortality', 'trend']
    ai_summary = "Run 'Load CDC Data' first to generate AI summary."
    if any(word in query.lower() for word in keywords):
        st.success(f"Dashboard Response: {ai_summary}")
    else:
        st.error("Dashboard Response: Sorry, I can only answer COVID-related mortality queries yet.")
