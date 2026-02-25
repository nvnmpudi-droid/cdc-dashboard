"""
OSIS – Pipeline Orchestrator (v1.0)
=====================================
Runs the full neuro-symbolic pipeline in sequence:
  1. database_init.py  → ingest CDC data → canonical_metrics
  2. analysis.py       → LogicAgent → Z-scores → logic_output.json
  3. summarization.py  → TinyLlama → strategic_brief.txt

Usage:
  python main.py                  # full pipeline
  python main.py --skip-db        # skip re-ingestion (DB already built)
  python main.py --no-llm         # skip TinyLlama, print fact packet only
"""

import json
import argparse
import sys
from pathlib import Path

from database_init import initialize_osis_db
from analysis import run_logic_audit


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║       OSIS — Organizational Strategy Intelligence    ║
║       Neuro-Symbolic Pipeline  v1.0                  ║
╚══════════════════════════════════════════════════════╝
""")


def print_fact_packet_summary(fact_packet: dict):
    """Fallback output when Ollama is not available."""
    p = fact_packet.get("payload", {})
    a = p.get("analysis", {})
    b = p.get("baseline_stats", {})

    print("""
╔══════════════════════════════════════════════════════╗
║         OSIS FACT PACKET  (No-LLM Mode)              ║
╚══════════════════════════════════════════════════════╝""")
    print(f"  Jurisdiction : {p.get('state')}")
    print(f"  Date         : {str(p.get('timestamp', ''))[:10]}")
    print(f"  Observed     : {p.get('observed_value', 0):,.0f} deaths")
    print(f"  Baseline     : {b.get('rolling_mean', 0):,.0f} (4-week mean)")
    print(f"  Z-Score      : {a.get('z_score', 0):.4f}")
    print(f"  Severity     : {a.get('severity')}")
    print(f"  Anomaly      : {'YES' if a.get('anomaly_detected') else 'NO'}")
    print(f"\n  Historic anomalies : {a.get('total_anomalies_in_history', 0)}")
    print(f"  Historic critical  : {a.get('total_critical_in_history', 0)}")

    # Plain-language interpretation without LLM
    z = a.get("z_score", 0)
    if z < -2.0:
        print(f"""
  ── Interpretation (deterministic) ──────────────────
  Z-score of {z:.2f} is strongly negative.
  In CDC surveillance this typically indicates DATA
  REPORTING LAG — certificates not yet processed,
  not a genuine mortality drop.
  Recommendation: Validate reporting pipeline before
  acting on this figure.
""")
    elif z > 2.0:
        print(f"""
  ── Interpretation (deterministic) ──────────────────
  Z-score of {z:.2f} signals EXCESS MORTALITY.
  Observed deaths exceed the 4-week baseline by
  {abs(z):.1f} standard deviations.
  Recommendation: Escalate to epidemiological review.
""")
    else:
        print("\n  System operating within normal parameters.\n")


def run_pipeline(skip_db: bool = False, use_llm: bool = True):
    print_banner()

    # ── STEP 1: Database / Ingestion ─────────────────────────────────────────
    if skip_db:
        print("⏭️  Step 1: Skipping DB init (--skip-db flag set)\n")
    else:
        print("━" * 55)
        print("  STEP 1 — Data Ingestion & Archive")
        print("━" * 55)
        initialize_osis_db()

    # ── STEP 2: Logic Agent ───────────────────────────────────────────────────
    print("━" * 55)
    print("  STEP 2 — Logic Agent (Z-Score Audit)")
    print("━" * 55)
    fact_packet = run_logic_audit(
        domain="public_health",
        metric_name="weekly_deaths_all_cause",
        state_filter="United States",
        export_json=True
    )

    if fact_packet.get("status") != "success":
        print(f"❌ Logic Agent failed: {fact_packet.get('message')}")
        sys.exit(1)

    # ── STEP 3: Inference Agent ───────────────────────────────────────────────
    print("━" * 55)
    print("  STEP 3 — Inference Agent (Strategic Brief)")
    print("━" * 55)

    if not use_llm:
        print("⏭️  LLM disabled (--no-llm flag). Printing Fact Packet instead.\n")
        print_fact_packet_summary(fact_packet)
        return

    # Check if Ollama is reachable before importing summarization
    try:
        import requests
        requests.get("http://127.0.0.1:11434/", timeout=3)
        llm_available = True
    except Exception:
        llm_available = False

    if not llm_available:
        print("⚠️  Ollama is not running — falling back to deterministic output.")
        print("   To enable TinyLlama: run  'ollama serve'  in a separate terminal")
        print("   Then pull the model:  'ollama pull tinyllama'\n")
        print_fact_packet_summary(fact_packet)
        return

    from summarization import generate_strategic_brief
    brief = generate_strategic_brief(input_file="logic_output.json", export=True)

    if not brief:
        print("⚠️  LLM returned empty response — printing Fact Packet instead.")
        print_fact_packet_summary(fact_packet)
        return

    # ── DONE ─────────────────────────────────────────────────────────────────
    print("━" * 55)
    print("  ✅  OSIS Pipeline Complete")
    print("━" * 55)
    print("  Outputs:")
    print("    logic_output.json    → LogicAgent Fact Packet")
    print("    strategic_brief.txt  → Governed Strategic Brief")
    print("━" * 55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OSIS Pipeline Orchestrator")
    parser.add_argument("--skip-db", action="store_true",
                        help="Skip DB re-ingestion (use existing archive)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip TinyLlama, output deterministic brief only")
    args = parser.parse_args()

    run_pipeline(skip_db=args.skip_db, use_llm=not args.no_llm)