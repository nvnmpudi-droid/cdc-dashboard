def filter_recent_years(df, year=2020):
    df_filtered = df[df['Year'] >= year]
    return df_filtered
