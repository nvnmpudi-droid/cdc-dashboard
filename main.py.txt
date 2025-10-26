from data_ingest import fetch_cdc_data
from processing import filter_recent_years
from analysis import summarize_covid_deaths
from dashboard import plot_covid_deaths
from summarization import ai_narrative_summary

def query_dashboard(query, ai_summary):
    keywords = ['covid', 'death', 'mortality', 'trend']
    if any(word in query.lower() for word in keywords):
        print("Dashboard Response:", ai_summary)
    else:
        print("Dashboard Response: Sorry, I can only answer COVID-related mortality queries yet.")

def main():
    df = fetch_cdc_data()
    df_filtered = filter_recent_years(df)
    incidence_summary = summarize_covid_deaths(df_filtered)
    plot_covid_deaths(incidence_summary)
    ai_summary = ai_narrative_summary(incidence_summary)
    query_dashboard("What is the trend for COVID mortality?", ai_summary)

if __name__ == "__main__":
    main()
