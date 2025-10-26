# prompt_templates.py
# Build reusable and dynamic prompt templates to guide your LLM outputs.

from langchain.prompts import PromptTemplate, ChatPromptTemplate

def mortality_summary_prompt():
    return PromptTemplate.from_template(
        "Summarize the data: {data_summary}. Highlight the trend for {metric} between {start_year} and {end_year}."
    )

def chat_prompt_template():
    return ChatPromptTemplate.from_messages([
        ("system", "You are a CDC data analyst providing insights."),
        ("user", "{question}")
    ])
