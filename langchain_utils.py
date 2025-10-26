# langchain_utils.py
# Lightweight utilities for LLM interactions and context-aware responses.

from langchain_openai import ChatOpenAI

def get_llm(model="gpt-4o-mini", temperature=0.2):
    """Centralized LLM factory."""
    return ChatOpenAI(model_name=model, temperature=temperature)


def generate_text_response(prompt, model="gpt-4o-mini"):
    llm = get_llm(model=model)
    return llm.predict(prompt)
