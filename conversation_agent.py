
import json, re
from dataset_config import get_default_config

TRANSLATION_PROMPT = """You are a query translator for a statistical anomaly detection system.
Convert the user query into structured JSON. Return ONLY valid JSON, no prose, no markdown.

Required fields:
  dataset_id: one of {dataset_ids}
  entity_filter: string or "default"
  time_filter: "7d" | "30d" | "90d" | "1y" | "all"
  analysis_type: "anomaly" | "forecast" | "both"
  ambiguous: true/false
  clarification_needed: string or null

User query: {query}

JSON only:"""

def translate_query(user_query: str, available_datasets: list) -> dict:
    """LLM Role 1 — translate free text to structured query. Vocal cord discipline applies."""
    dataset_ids = [d["id"] for d in available_datasets]
    try:
        import requests
        requests.get("http://127.0.0.1:11434/", timeout=3)
    except:
        return _fallback_translation(user_query, dataset_ids)
    try:
        import requests
        prompt = TRANSLATION_PROMPT.format(
            dataset_ids=dataset_ids,
            query=user_query
        )
        r = requests.post("http://127.0.0.1:11434/api/generate",
            json={"model":"phi3:mini","prompt":prompt,"stream":False,"options":{"temperature":0.0}},
            timeout=60)
        raw = r.json().get("response","").strip()
        # Strip markdown fences if present
        raw = re.sub(r"```json|```","",raw).strip()
        parsed = json.loads(raw)
        # Schema validation — LLM output must conform
        required = ["dataset_id","entity_filter","time_filter","analysis_type"]
        for field in required:
            if field not in parsed:
                return _fallback_translation(user_query, dataset_ids)
        if parsed["dataset_id"] not in dataset_ids:
            parsed["dataset_id"] = dataset_ids[0]
        return parsed
    except Exception as e:
        return _fallback_translation(user_query, dataset_ids)

def _fallback_translation(query: str, dataset_ids: list) -> dict:
    """Deterministic fallback when LLM unavailable or output invalid."""
    q = query.lower()
    time_filter = "30d"
    if any(w in q for w in ["year","annual","12 month"]): time_filter = "1y"
    elif any(w in q for w in ["week","7 day"]): time_filter = "7d"
    elif any(w in q for w in ["quarter","90"]): time_filter = "90d"
    analysis = "both"
    if "forecast" in q or "predict" in q: analysis = "forecast"
    elif "anomaly" in q or "spike" in q or "drop" in q: analysis = "anomaly"
    return {
        "dataset_id": dataset_ids[0] if dataset_ids else "cdc_mortality",
        "entity_filter": "default",
        "time_filter": time_filter,
        "analysis_type": analysis,
        "ambiguous": False,
        "clarification_needed": None,
        "translation_method": "deterministic_fallback"
    }

def contextualize(term: str) -> str:
    """LLM Role 4 — explain domain terms. Returns plain explanation."""
    CONTEXT = {
        "z-score": "A Z-score measures how many standard deviations a value is from the mean. Above +2.0 or below -2.0 is unusual. Above +3.0 or below -3.0 is rare.",
        "z_score": "A Z-score measures how many standard deviations a value is from the mean. Above +2.0 or below -2.0 is unusual.",
        "critical": "CRITICAL severity means the Z-score exceeds 3.0 standard deviations — a statistically rare event requiring investigation.",
        "warning": "WARNING severity means the Z-score is between 2.0 and 3.0 — unusual but not yet at the critical threshold.",
        "tamas": "TAMAS (inertia) indicates a suppressed or lagged signal — often a reporting artifact rather than a real event.",
        "rajas": "RAJAS (activity) indicates an active, unexplained anomaly that has persisted beyond the normal threshold.",
        "sattva": "SATTVA (clarity) indicates the system is operating within normal parameters.",
        "reporting lag": "A reporting lag occurs when death certificates or records are delayed in processing, causing a temporary artificial drop in reported numbers.",
        "prophet": "Prophet is a time-series forecasting model developed by Meta. It decomposes trends, seasonality, and holidays to produce forward-looking estimates with confidence intervals.",
        "pancavayava": "Pañcavayava is a five-member logical proof from Nyāya philosophy: Proposition, Reason, Historical Example, Application, and Conclusion.",
    }
    term_lower = term.lower().strip()
    for key, explanation in CONTEXT.items():
        if key in term_lower or term_lower in key:
            return explanation
    return f"Term '{term}' is not in the contextualization registry. Add it to conversation_agent.py CONTEXT dict."

if __name__ == "__main__":
    datasets = [{"id":"cdc_mortality"},{"id":"demo_hospital"}]
    result = translate_query("show me the worst anomaly this year", datasets)
    print("Translation:", json.dumps(result, indent=2))
    print("\nContext:", contextualize("z-score"))
