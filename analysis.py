import json
import duckdb
import pandas as pd
from datetime import datetime, timezone
from dataset_config import DatasetConfig, get_default_config

DB_NAME = "osis_strategic_archives.db"

def run_logic_audit(config=None, export_json=True):
    if config is None:
        config = get_default_config()
    print("="*55)
    print("  OSIS Logic Agent -- Anomaly Detection Audit")
    print("="*55)
    print(f"  Domain  : {config.domain}")
    print(f"  Metric  : {config.metric_name}")
    print(f"  Entity  : {config.entity_filter}")
    print("="*55)
    con = duckdb.connect(DB_NAME, read_only=True)
    try:
        count = con.execute("SELECT COUNT(*) FROM canonical_metrics WHERE domain=? AND metric_name=? AND state=?",
            [config.domain, config.metric_name, config.entity_filter]).fetchone()[0]
        if count == 0:
            available = con.execute("SELECT DISTINCT state FROM canonical_metrics WHERE domain=? AND metric_name=? LIMIT 10",
                [config.domain, config.metric_name]).fetchall()
            raise ValueError(f"No data for entity={config.entity_filter}. Available: {[r[0] for r in available]}")
        print(f"Found {count} records for {config.entity_filter}")
        df = con.execute(f"""
            WITH base AS (
                SELECT time_period, metric_value, state,
                AVG(metric_value) OVER (PARTITION BY state ORDER BY time_period ROWS BETWEEN {config.rolling_window} PRECEDING AND 1 PRECEDING) AS rolling_mean,
                STDDEV(metric_value) OVER (PARTITION BY state ORDER BY time_period ROWS BETWEEN {config.rolling_window} PRECEDING AND 1 PRECEDING) AS rolling_std
                FROM canonical_metrics WHERE domain=? AND metric_name=? AND state=? ORDER BY time_period)
            SELECT time_period, metric_value, state,
            ROUND(rolling_mean,2) AS rolling_mean, ROUND(rolling_std,2) AS rolling_std,
            CASE WHEN rolling_std>0 THEN ROUND((metric_value-rolling_mean)/rolling_std,4) ELSE 0.0 END AS z_score
            FROM base WHERE rolling_mean IS NOT NULL AND rolling_std IS NOT NULL
        """, [config.domain, config.metric_name, config.entity_filter]).df()
        def classify(z):
            az = abs(z)
            if az >= config.critical_threshold: return "CRITICAL"
            elif az >= config.anomaly_threshold: return "WARNING"
            return "NORMAL"
        df["severity"] = df["z_score"].apply(classify)
        df["anomaly_detected"] = df["severity"] != "NORMAL"
        anomalies = df[df["anomaly_detected"]].copy()
        critical  = df[df["severity"]=="CRITICAL"].copy()
        latest    = df.iloc[-1]
        print(f"Total anomalies: {len(anomalies)} | Critical: {len(critical)}")
        print(f"Latest: {latest['time_period']} Z={latest['z_score']:.4f} {latest['severity']}")
        if not anomalies.empty:
            top = anomalies.sort_values("z_score",ascending=False).head(10)[["time_period","metric_value","rolling_mean","z_score","severity"]]
            print(top.to_string(index=False))
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
                "baseline_stats": {"rolling_mean": float(latest["rolling_mean"]), "rolling_std": float(latest["rolling_std"]), "window_periods": config.rolling_window, "total_observations": len(df)},
                "analysis": {"z_score": float(latest["z_score"]), "anomaly_detected": bool(latest["anomaly_detected"]), "severity": str(latest["severity"]), "total_anomalies_in_history": len(anomalies), "total_critical_in_history": len(critical)},
                "top_anomalies": [{"date": str(r["time_period"]), "value": float(r["metric_value"]), "z_score": float(r["z_score"]), "severity": str(r["severity"])} for _,r in anomalies.sort_values("z_score",ascending=False).head(5).iterrows()]
            }
        }
        if export_json:
            with open("logic_output.json","w") as f: json.dump(fact_packet,f,indent=2)
            print("Fact Packet saved -> logic_output.json")
        return fact_packet
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        con.close()
