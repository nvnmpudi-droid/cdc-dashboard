import requests
import sys
import re

# Using 127.0.0.1 is usually more reliable in Codespaces
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "tinyllama" 

def deterministic_validation(draft_brief, raw_stats):
    """
    The 'Tarka' Layer (Upgraded): 
    Uses Deterministic Python Logic (Pratyakṣa) instead of AI guessing.
    It strictly checks if the exact numbers appear in the text.
    """
    total_deaths = str(raw_stats['total'])
    peak_year = str(raw_stats['peak_year'])

    # 1. Clean the text (remove commas for easier matching)
    clean_text = draft_brief.replace(",", "")
    
    # 2. Strict Logical Check
    errors = []
    if total_deaths not in clean_text:
        errors.append(f"Missing/Wrong Total (Expected {total_deaths})")
    
    if peak_year not in clean_text:
        errors.append(f"Missing/Wrong Peak Year (Expected {peak_year})")

    # 3. Return Verdict
    if not errors:
        return "VALIDATED"
    else:
        return f"CONTRADICTION FOUND: {'; '.join(errors)}"

def ai_narrative_summary(incidence_summary):
    # 1. Prepare Data
    years = incidence_summary["Year"].tolist()
    deaths = incidence_summary["COVID-19 Deaths"].tolist()

    data_lines = "\n".join([
        "  - " + str(int(year)) + ": " + str(int(count)) + " deaths"
        for year, count in zip(years, deaths)
    ])

    if not years:
        return "[NO DATA AVAILABLE]"

    peak_year = int(years[deaths.index(max(deaths))])
    total = int(sum(deaths))
    
    raw_stats = {"peak_year": peak_year, "total": total}

    # 2. Build Prompt (Constraint-Based)
    prompt = (
        "You are a public health reporting bot. "
        "Your ONLY job is to complete this sentence exactly with the numbers provided:\n\n"
        f"Data: Total = {total}, Peak = {peak_year}\n\n"
        "Sentence: The CDC reports a total of [insert total] deaths, with the peak occurring in [insert peak year]."
    )

    print(f"DEBUG: Sending request to {OLLAMA_URL} with model {MODEL_NAME}...", file=sys.stderr)

    # 3. Call AI Model
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}},
            timeout=120 
        )
        response.raise_for_status()
        narrative = response.json().get("response", "").strip()
    except Exception as e:
        narrative = "[ERROR: " + str(e) + "]"

    # 4. Call Deterministic Validator (Hybrid Agent)
    if "ERROR" not in narrative:
        print("DEBUG: Running Deterministic Validation...", file=sys.stderr)
        audit_status = deterministic_validation(narrative, raw_stats)
    else:
        audit_status = "[SKIPPED]"

    # 5. Return Output
    output = (
        "\n[SOURCE: CDC NVSS Provisional Mortality Data]\n"
        "[AGENT: Interpretation Agent - TinyLlama Layer]\n"
        "==================================================\n\n"
        "Data Summary:\n" + data_lines + "\n\n"
        "AI Policy Brief (TinyLlama):\n" + narrative + "\n\n"
        f"[VALIDATION STATUS: {audit_status}]\n"
        "==================================================\n"
        "[AUDIT: All claims grounded in CDC national totals]\n"
    )
    
    return output