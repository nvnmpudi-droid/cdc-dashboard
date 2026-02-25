"""
OSIS – Inference Agent / Summarization Layer (v1.4)
====================================================
Fix: Commentary truncation and COVID drift.
  - Reject commentary that ends without punctuation (truncated)
  - Reject commentary mentioning COVID (wrong domain — this is all-cause)
  - Reject commentary over 200 chars (TinyLlama is rambling)
"""

import json
import re
import requests
from datetime import datetime, timezone

OLLAMA_URL  = "http://127.0.0.1:11434/api/chat"
MODEL_NAME  = "tinyllama"
INPUT_FILE  = "logic_output.json"
OUTPUT_FILE = "strategic_brief.txt"


def deterministic_brief(payload: dict) -> str:
    state  = payload["state"]
    date   = payload["timestamp"][:10]
    value  = int(payload["observed_value"])
    z      = payload["analysis"]["z_score"]
    mean   = int(payload["baseline_stats"]["rolling_mean"])
    n_crit = payload["analysis"]["total_critical_in_history"]
    n_anom = payload["analysis"]["total_anomalies_in_history"]

    if z < -2.0:
        s1 = (f"For the week ending {date}, {state} recorded {value:,} all-cause deaths, "
              f"which is {abs(z):.2f} standard deviations below the 4-week rolling mean of {mean:,}.")
        s2 = ("In CDC mortality surveillance, a strongly negative Z-score in the most recent "
              "weeks is characteristic of data reporting lag — death certificates are still "
              "being processed and have not yet been fully counted, not a genuine mortality decline.")
        s3 = (f"Do not act on this figure as a real trend; validate the reporting pipeline "
              f"and reassess in 4 to 6 weeks when the data matures "
              f"(this dataset contains {n_crit} prior CRITICAL events across {n_anom} total anomalies).")
    elif z > 2.0:
        s1 = (f"For the week ending {date}, {state} recorded {value:,} all-cause deaths, "
              f"which is {z:.2f} standard deviations above the 4-week rolling mean of {mean:,}.")
        s2 = (f"This positive deviation represents genuine excess mortality; "
              f"the historical record shows {n_crit} prior CRITICAL events in this dataset, "
              f"confirming that surges of this magnitude have occurred before and require immediate attention.")
        s3 = ("Escalate to epidemiological review immediately, cross-reference with cause-specific "
              "mortality data, and prepare resource surge protocols for affected jurisdictions.")
    else:
        s1 = (f"For the week ending {date}, {state} recorded {value:,} all-cause deaths, "
              f"with a Z-score of {z:.2f} relative to the 4-week rolling mean of {mean:,}.")
        s2 = ("This observation falls within normal statistical bounds, "
              "indicating stable mortality patterns with no significant deviation from baseline.")
        s3 = (f"Continue routine surveillance monitoring; "
              f"note that this dataset has recorded {n_crit} CRITICAL events historically, "
              "so ongoing vigilance remains appropriate.")

    return f"{s1} {s2} {s3}"


def llm_commentary(payload: dict) -> str | None:
    z = payload["analysis"]["z_score"]

    if z < -2.0:
        question = "In one sentence, why do CDC mortality reports show lower death counts in the most recent weeks compared to earlier weeks?"
    elif z > 2.0:
        question = "In one sentence, why does excess all-cause mortality require epidemiological investigation beyond just counting deaths?"
    else:
        question = "In one sentence, why is routine mortality surveillance valuable even when no anomalies are detected?"

    messages = [
        {
            "role": "system",
            "content": (
                "You are a public health expert. "
                "Answer in exactly one complete sentence under 180 characters. "
                "Do not mention COVID-19 specifically. "
                "Do not use bullet points or lists."
            )
        },
        {"role": "user", "content": question}
    ]

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 60}
            },
            timeout=60
        )
        response.raise_for_status()
        sentence = response.json()["message"]["content"].strip()

        # Reject if truncated
        if not sentence or sentence[-1] not in ".!?":
            return None
        # Reject if too long (rambling)
        if len(sentence) > 250:
            return None
        # Reject if multiple sentences
        if sentence.count(".") > 2:
            return None
        # Reject if mentions COVID (wrong framing for all-cause data)
        if any(w in sentence.lower() for w in ["covid", "coronavirus", "pandemic", "vaccine"]):
            return None
        # Reject hallucinated large numbers
        for n_str in re.findall(r"\b[\d,]+\b", sentence):
            if int(n_str.replace(",", "")) > 500_000:
                return None

        return sentence

    except Exception:
        return None


def generate_strategic_brief(input_file: str = INPUT_FILE, export: bool = True) -> str:

    print(f"\n{'='*55}")
    print(f"  🏛️  OSIS Inference Agent — Strategic Brief v1.4")
    print(f"{'='*55}\n")

    print(f"📂 Loading: {input_file}")
    try:
        with open(input_file) as f:
            logic_output = json.load(f)
    except FileNotFoundError:
        print(f"❌ {input_file} not found. Run analysis.py first.")
        return ""

    if logic_output.get("status") != "success":
        print(f"❌ Fact Packet error: {logic_output.get('message')}")
        return ""

    payload = logic_output["payload"]
    print(f"   ✅ {payload['metric_name']} | {payload['state']} | {payload['timestamp'][:10]}\n")

    # Step 1: Deterministic brief (always — this is the Tarka ground truth)
    print("📝 Step 1: Generating deterministic brief...")
    core_brief = deterministic_brief(payload)
    print("   ✅ Done\n")

    # Step 2: Optional LLM commentary (one sentence, tightly filtered)
    print(f"🤖 Step 2: Requesting commentary from {MODEL_NAME}...")
    commentary = None
    try:
        requests.get("http://127.0.0.1:11434/", timeout=3)
        commentary = llm_commentary(payload)
        if commentary:
            print(f"   ✅ Commentary accepted: \"{commentary[:80]}...\"\n")
        else:
            print(f"   ⚠️  Commentary rejected by Tarka filter — brief stands alone\n")
    except Exception:
        print(f"   ⚠️  Ollama not reachable — skipping\n")

    # Combine
    brief = core_brief
    if commentary:
        brief = f"{core_brief}\n\n[Context] {commentary}"

    # Print
    z   = payload["analysis"]["z_score"]
    sev = payload["analysis"]["severity"]
    print(f"{'='*55}")
    print(f"  📋 GOVERNED STRATEGIC BRIEF")
    print(f"  Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Z-Score   : {z} | Severity: {sev}")
    print(f"  Core      : deterministic ✅")
    print(f"  Commentary: {'tinyllama ✅' if commentary else 'skipped (filtered)'}")
    print(f"{'='*55}\n")
    print(brief)
    print(f"\n{'='*55}\n")

    if export:
        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_fact_packet": input_file,
            "model": MODEL_NAME,
            "core_source": "deterministic",
            "commentary_source": MODEL_NAME if commentary else None,
            "brief": brief
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(out, f, indent=2)
        print(f"✅ Brief saved → {OUTPUT_FILE}\n")

    return brief


if __name__ == "__main__":
    generate_strategic_brief()