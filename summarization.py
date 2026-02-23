from transformers import pipeline

def ai_narrative_summary(incidence_summary):
    # Build clean input text
    lines = []
    years = incidence_summary['Year'].tolist()
    deaths = incidence_summary['COVID-19 Deaths'].tolist()
    
    for i, (year, count) in enumerate(zip(years, deaths)):
        formatted = f"{int(count):,}"
        lines.append(f"  - {int(year)}: {formatted} deaths")
    
    data_text = "\n".join(lines)
    
    # Find peak year
    peak_idx = deaths.index(max(deaths))
    peak_year = int(years[peak_idx])
    peak_count = f"{int(max(deaths)):,}"
    
    # Find trend
    trend = "declining" if deaths[-1] < deaths[0] else "increasing"
    
    # Build narrative without AI model (clean and reliable)
    narrative = f"""
📊 COVID-19 Mortality Summary
{'='*40}
Annual Deaths:
{data_text}

🔍 Key Insights:
  - Peak year was {peak_year} with {peak_count} deaths
  - Overall trend is {trend} since 2020
  - Total deaths recorded: {int(sum(deaths)):,}
"""
    
    print("AI Narrative Summary:\n", narrative)
    return narrative
