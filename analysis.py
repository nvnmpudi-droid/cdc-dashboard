def summarize_covid_deaths(df_filtered):
    # Filter to national totals only to avoid double counting
    df_national = df_filtered[
        (df_filtered['State'] == 'United States') &
        (df_filtered['Sex'] == 'All Sexes') &
        (df_filtered['Age Group'] == 'All Ages') &
        (df_filtered['Group'] == 'By Year')
    ]
    incidence_summary = df_national.groupby('Year')['COVID-19 Deaths'].sum().reset_index()
    print(incidence_summary)
    return incidence_summary
