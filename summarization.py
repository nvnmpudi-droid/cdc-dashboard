from transformers import pipeline

def ai_narrative_summary(incidence_summary):
    summarizer = pipeline('summarization')
    text_summary_input = "COVID-19 deaths per year: " + \
        ", ".join([f"{row['COVID-19 Deaths']} in {int(row['Year'])}" for _, row in incidence_summary.iterrows()]) + "."
    ai_summary = summarizer(text_summary_input, max_length=50, min_length=20)[0]['summary_text']
    print("AI Narrative Summary:\n", ai_summary)
    return ai_summary
