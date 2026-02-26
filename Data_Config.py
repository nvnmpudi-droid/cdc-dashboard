"""
OSIS – Logic Agent / Analysis Layer (v2.0)
==========================================
Domain-agnostic rewrite. Accepts any DatasetConfig object.
Hardcoded CDC references removed — config drives all queries.

SOVEREIGNTY RULE:
  - Reads canonical_metrics with read_only=True
  - Never writes to canonical_metrics
  - Outputs only to logic_output.json (Vaikhari contract)
"""

import json
import duckdb
import pandas as pd
from datetime import datetime, timezone
from dataset_config import DatasetConfig, get_default_config

DB_NAME = "osis_strategic_archives.db"


def run_logic_audit(
    config: DatasetConfig = None,
    export_json: bool = True
) -> dict:

    if config is None:
        config = get_default_config()

    print(f"\n{'='*55}")
    print(f"  🧠 OSIS Logic Agent — Anomaly Detection Audit")
    print(f"{'='*55}")
    print(f"  Domain  : {config.domain}")
    print(f"  Metric  : {config.metric_name}")
    print(f"  Entity  : {config.entity_filter}")
    print(f"{'='*55}\n")

    con = duckdb.connect(DB_NAME, read_only=True)

    try:
        # ── STEP 1: Verify data exists ────────────────────────────────────────
        count = con.execute("""
            SELECT COUNT(*) FROM canonical_metrics
            WHERE domain = ? AND metric_name = ? AND state = ?
        """, [config.domain, config.metric_name, config.entity_filter]).fetchone()[0]

        if count == 0:
            available = con.execute("""
                SELECT DISTINCT state FROM canonical_metrics
                WHERE domain = ? AND metric_name = ?
                ORDER BY state LIMIT 10
            """, [config.domain, config.metric_name]).fetchall()
            available_entities = [r[0] for r in available]
            raise ValueError(
                f"No data for entity='{config.entity_filter}'. "
                f"Available (sample): {available_entities}"
            )

        print(f"📊 Step 1: Found {count:,} records for '{config.entity_filter}'")

        # ── STEP 2: Compute rolling Z-scores ─────────────────────────────────
        print(f"🔍 Step 2: Computing rolling {config.rolling_window}-period Z-scores...")

        df = con.execute(f"""
            WITH base AS (
                SELECT
                    time_period,
                    metric_value,
                    state,
                    AVG(metric_value) OVER (
                        PARTITION BY state
                        ORDER BY time_period
                        ROWS BETWEEN {config.rolling_window} PRECEDING AND 1 PRECEDING
                    ) AS rolling_mean,
                    STDDEV(metric_value) OVER (
                        PARTITION BY state
                        ORDER BY time_period
                        ROWS BETWEEN {config.rolling_window} PRECEDING AND 1 PRECEDING
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
                ROUND(rolling_mean, 2) AS rolling_mean,
                ROUND(rolling_std, 2)  AS rolling_std,
                CASE
                    WHEN rolling_std > 0
                    THEN ROUND((metric_value - rolling_mean) / rolling_std, 4)
                    ELSE 0.0
                END AS z_score
            FROM base
            WHERE rolling_mean IS NOT NULL
              AND rolling_std  IS NOT NULL
        """, [config.domain, config.metric_name, config.entity_filter]).df()

        print(f"   ✅ Computed Z-scores for {len(df):,} observations\n")

        # ── STEP 3: Classify anomalies ────────────────────────────────────────
        print(f"🚩 Step 3: Classifying anomalies "
              f"(threshold: ±{config.anomaly_threshold}σ)...")

        def classify(z):
            az = abs(z)
            if az >= config.critical_threshold:
                return "CRITICAL"
            elif az >= config.anomaly_threshold:
                return "WARNING"
            return "NORMAL"

        df["severity"] = df["z_score"].apply(classify)
        df["anomaly_detected"] = df["severity"] != "NORMAL"

        anomalies = df[df["anomaly_detected"]].copy()
        critical  = df[df["severity"] == "CRITICAL"].copy()

        print(f"   Total anomalies (≥{config.anomaly_threshold}σ) : {len(anomalies):,}")
        print(f"   Critical events (≥{config.critical_threshold}σ) : {len(critical):,}\n")

        # ── STEP 4: Latest observation ────────────────────────────────────────
        latest = df.iloc[-1]
        print(f"📌 Step 4: Latest Observation")
        print(f"   Date          : {latest['time_period']}")
        print(f"   Value         : {latest['metric_value']:,.0f}")
        print(f"   Rolling Mean  : {latest['rolling_mean']:,.0f}")
        print(f"   Z-Score       : {latest['z_score']:.4f}")
        print(f"   Severity      : {latest['severity']}\n")

        # ── STEP 5: Top anomalies ─────────────────────────────────────────────
        if not anomalies.empty:
            print(f"🔴 Step 5: Top Anomalies by Z-Score")
            top = (
                anomalies
                .sort_values("z_score", ascending=False)
                .head(10)[["time_period", "metric_value",
                           "rolling_mean", "z_score", "severity"]]
            )
            print(top.to_string(index=False))
        else:
            print(f"✅ Step 5: No anomalies — system operating normally.")

        # ── STEP 6: Build Vaikhari contract (Fact Packet) ─────────────────────
        print(f"\n📝 Step 6: Building Fact Packet for Inference Agent...")

        fact_packet = {
            "status": "success",
            "schema_version": config.schema_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "domain": config.domain,
                "metric_name": config.metric_name,
                "state": config.entity_filter,
                "timestamp": str(latest["time_period"]),
                "observed_value": float(latest["metric_value"]),
                "baseline_stats": {
                    "rolling_mean": float(latest["rolling_mean"]),
                    "rolling_std":  float(latest["rolling_std"]),
                    "window_periods": config.rolling_window,
                    "total_observations": len(df)
                },
                "analysis": {
                    "z_score": float(latest["z_score"]),
                    "anomaly_detected": bool(latest["anomaly_detected"]),
                    "severity": str(latest["severity"]),
                    "total_anomalies_in_history": int(len(anomalies)),
                    "total_critical_in_history":  int(len(critical)),
                },
                "top_anomalies": [
                    {
                        "date":     str(row["time_period"]),
                        "value":    float(row["metric_value"]),
                        "z_score":  float(row["z_score"]),
                        "severity": str(row["severity"])
                    }
                    for _, row in anomalies
                    .sort_values("z_score", ascending=False)
                    .head(5).iterrows()
                ]
            }
        }

        if export_json:
            with open("logic_output.json", "w") as f:
                json.dump(fact_packet, f, indent=2)
            print(f"   ✅ Fact Packet saved → logic_output.json\n")

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
    result = run_logic_audit()
    if result.get("status") == "success":
        z   = result["payload"]["analysis"]["z_score"]
        sev = result["payload"]["analysis"]["severity"]
        print(f"  Z-Score  : {z}")
        print(f"  Severity : {sev}")