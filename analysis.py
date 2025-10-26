def summarize_covid_deaths(df_filtered):
    incidence_summary = df_filtered.groupby('Year')['COVID-19 Deaths'].sum().reset_index()
    print(incidence_summary)
    return incidence_summary
