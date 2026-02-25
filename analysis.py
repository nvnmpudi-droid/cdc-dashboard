"""
OSIS – Logic Agent / Analysis Layer (v1.0)
==========================================
The "Sensory Cortex" of OSIS.

What it does:
  1. Reads from canonical_metrics (built by database_init.py)
  2. Computes rolling Z-scores per state per metric
  3. Flags anomalies deterministically — no LLM involved
  4. Exports a structured JSON "Fact Packet" ready for TinyLlama

Column contract (matches database_init.py output):
  canonical_metrics → domain, metric_name, time_period, metric_value, state
"""

import json
import duckdb
import pandas as pd
from datetime import datetime, timezone

DB_NAME = "osis_strategic_archives.db"
ANOMALY_THRESHOLD = 2.0   # Z-score ≥ 2.0 → WARNING
CRITICAL_THRESHOLD = 3.0  # Z-score ≥ 3.0 → CRITICAL
ROLLING_WINDOW = 4        # weeks of history for baseline


def run_logic_audit(
    domain: str = "public_health",
    metric_name: str = "weekly_deaths_all_cause",
    state_filter: str = "United States",
    export_json: bool = True
) -> dict:

    print(f"\n{'='*55}")
    print(f"  🧠 OSIS Logic Agent — Anomaly Detection Audit")
    print(f"{'='*55}")
    print(f"  Domain  : {domain}")
    print(f"  Metric  : {metric_name}")
    print(f"  State   : {state_filter}")
    print(f"{'='*55}\n")

    con = duckdb.connect(DB_NAME, read_only=True)

    try:
        # ── STEP 1: Verify data exists ────────────────────────────────────────
        count = con.execute("""
            SELECT COUNT(*) FROM canonical_metrics
            WHERE domain = ? AND metric_name = ? AND state = ?
        """, [domain, metric_name, state_filter]).fetchone()[0]

        if count == 0:
            # Try without state filter and show what states exist
            available = con.execute("""
                SELECT DISTINCT state FROM canonical_metrics
                WHERE domain = ? AND metric_name = ?
                ORDER BY state LIMIT 10
            """, [domain, metric_name]).fetchall()
            available_states = [r[0] for r in available]
            raise ValueError(
                f"No data for state='{state_filter}'. "
                f"Available states (sample): {available_states}"
            )

        print(f"📊 Step 1: Found {count:,} records for '{state_filter}'")

        # ── STEP 2: Compute rolling Z-scores in DuckDB ───────────────────────
        # Using correct column names: time_period, metric_value, state
        print(f"🔍 Step 2: Computing rolling {ROLLING_WINDOW}-week Z-scores...")

        df = con.execute(f"""
            WITH base AS (
                SELECT
                    time_period,
                    metric_value,
                    state,
                    AVG(metric_value) OVER (
                        PARTITION BY state
                        ORDER BY time_period
                        ROWS BETWEEN {ROLLING_WINDOW} PRECEDING AND 1 PRECEDING
                    ) AS rolling_mean,
                    STDDEV(metric_value) OVER (
                        PARTITION BY state
                        ORDER BY time_period
                        ROWS BETWEEN {ROLLING_WINDOW} PRECEDING AND 1 PRECEDING
                    ) AS rolling_std
                FROM canonical_metrics
                WHERE domain = ?
                  AND metric_name = ?
                  AND state = ?
                ORDER BY time_period
            )
            SELECT
                time_period,
                metric_value,
                state,
                ROUND(rolling_mean, 2)  AS rolling_mean,
                ROUND(rolling_std, 2)   AS rolling_std,
                CASE
                    WHEN rolling_std > 0
                    THEN ROUND((metric_value - rolling_mean) / rolling_std, 4)
                    ELSE 0.0
                END AS z_score
            FROM base
            WHERE rolling_mean IS NOT NULL
              AND rolling_std IS NOT NULL
        """, [domain, metric_name, state_filter]).df()

        print(f"   ✅ Computed Z-scores for {len(df):,} observations\n")

        # ── STEP 3: Classify anomalies ────────────────────────────────────────
        print(f"🚩 Step 3: Classifying anomalies (threshold: ±{ANOMALY_THRESHOLD}σ)...")

        def classify(z):
            az = abs(z)
            if az >= CRITICAL_THRESHOLD:
                return "CRITICAL"
            elif az >= ANOMALY_THRESHOLD:
                return "WARNING"
            return "NORMAL"

        df["severity"] = df["z_score"].apply(classify)
        df["anomaly_detected"] = df["severity"] != "NORMAL"

        anomalies = df[df["anomaly_detected"]].copy()
        critical  = df[df["severity"] == "CRITICAL"].copy()

        print(f"   Total anomalies (≥2σ) : {len(anomalies):,}")
        print(f"   Critical events (≥3σ) : {len(critical):,}\n")

        # ── STEP 4: Latest observation summary ───────────────────────────────
        latest = df.iloc[-1]
        print(f"📌 Step 4: Latest Observation")
        print(f"   Date          : {latest['time_period']}")
        print(f"   Value         : {latest['metric_value']:,.0f}")
        print(f"   Rolling Mean  : {latest['rolling_mean']:,.0f}")
        print(f"   Z-Score       : {latest['z_score']:.4f}")
        print(f"   Severity      : {latest['severity']}\n")

        # ── STEP 5: Top anomalies table ───────────────────────────────────────
        if not anomalies.empty:
            print(f"🔴 Step 5: Top Anomalies by Z-Score")
            top = (
                anomalies
                .sort_values("z_score", ascending=False)
                .head(10)[["time_period", "metric_value", "rolling_mean", "z_score", "severity"]]
            )
            print(top.to_string(index=False))
        else:
            print(f"✅ Step 5: No anomalies detected — system operating normally.")

        # ── STEP 6: Build Fact Packet JSON for TinyLlama ─────────────────────
        print(f"\n📝 Step 6: Building Fact Packet for Inference Agent...")

        fact_packet = {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "domain": domain,
                "metric_name": metric_name,
                "state": state_filter,
                "timestamp": str(latest["time_period"]),
                "observed_value": float(latest["metric_value"]),
                "baseline_stats": {
                    "rolling_mean": float(latest["rolling_mean"]),
                    "rolling_std": float(latest["rolling_std"]),
                    "window_weeks": ROLLING_WINDOW,
                    "total_observations": len(df)
                },
                "analysis": {
                    "z_score": float(latest["z_score"]),
                    "anomaly_detected": bool(latest["anomaly_detected"]),
                    "severity": str(latest["severity"]),
                    "total_anomalies_in_history": int(len(anomalies)),
                    "total_critical_in_history": int(len(critical)),
                },
                "top_anomalies": [
                    {
                        "date": str(row["time_period"]),
                        "value": float(row["metric_value"]),
                        "z_score": float(row["z_score"]),
                        "severity": str(row["severity"])
                    }
                    for _, row in anomalies.sort_values("z_score", ascending=False).head(5).iterrows()
                ]
            }
        }

        if export_json:
            out_path = "logic_output.json"
            with open(out_path, "w") as f:
                json.dump(fact_packet, f, indent=2)
            print(f"   ✅ Fact Packet saved → {out_path}")
            print(f"   (This is the input TinyLlama will receive)\n")

        print(f"{'='*55}")
        print(f"  ✅ Logic Agent Audit Complete")
        print(f"{'='*55}\n")

        return fact_packet

    except Exception as e:
        print(f"\n❌ Logic Audit Failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        con.close()


if __name__ == "__main__":
    result = run_logic_audit(
        domain="public_health",
        metric_name="weekly_deaths_all_cause",
        state_filter="United States",
        export_json=True
    )

    # Quick sanity check
    if result.get("status") == "success":
        z = result["payload"]["analysis"]["z_score"]
        sev = result["payload"]["analysis"]["severity"]
        print(f"  Z-Score  : {z}")
        print(f"  Severity : {sev}")
        print(f"\n  → Ready for summarization.py (TinyLlama)\n")