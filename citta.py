
import duckdb, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "osis.db"

def init_citta():
    con = duckdb.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id            VARCHAR DEFAULT gen_random_uuid(),
            agent_id      VARCHAR NOT NULL,
            execution_ts  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            domain        VARCHAR,
            metric_name   VARCHAR,
            entity_filter VARCHAR,
            schema_version VARCHAR,
            input_hash    VARCHAR,
            output_hash   VARCHAR,
            tarka_result  VARCHAR,
            guna_state    VARCHAR,
            urgency       VARCHAR,
            z_score       DOUBLE,
            severity      VARCHAR,
            anomalies_found INTEGER,
            escalate      BOOLEAN,
            sutra_action  VARCHAR,
            pancavayava_complete BOOLEAN,
            execution_ms  INTEGER,
            notes         TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sutra_streak (
            metric_key    VARCHAR PRIMARY KEY,
            domain        VARCHAR,
            unmapped_streak INTEGER DEFAULT 0,
            last_seen_ts  TIMESTAMP,
            last_z_score  DOUBLE,
            guna_state    VARCHAR DEFAULT 'UNMAPPED'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS narration_log (
            id            VARCHAR DEFAULT gen_random_uuid(),
            execution_ts  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_id      VARCHAR,
            domain        VARCHAR,
            proof_hash    VARCHAR,
            narration     TEXT,
            firewall_result VARCHAR,
            word_count    INTEGER
        )
    """)
    con.close()
    print("Citta v1.0 initialized — agent_memory, sutra_streak, narration_log tables ready")

def append_memory(agent_id, domain, metric, entity, schema_version,
                  input_hash, output_hash, tarka_result, guna_state,
                  urgency=None, z_score=None, severity=None,
                  anomalies_found=None, escalate=False,
                  sutra_action=None, pancavayava_complete=False,
                  execution_ms=None, notes=None):
    con = duckdb.connect(DB_PATH)
    con.execute("""
        INSERT INTO agent_memory (
            agent_id, domain, metric_name, entity_filter, schema_version,
            input_hash, output_hash, tarka_result, guna_state, urgency,
            z_score, severity, anomalies_found, escalate, sutra_action,
            pancavayava_complete, execution_ms, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [agent_id, domain, metric, entity, schema_version,
          input_hash, output_hash, tarka_result, guna_state, urgency,
          z_score, severity, anomalies_found, escalate, sutra_action,
          pancavayava_complete, execution_ms, notes])
    con.close()

def log_narration(agent_id, domain, proof_hash, narration, firewall_result):
    con = duckdb.connect(DB_PATH)
    con.execute("""
        INSERT INTO narration_log (agent_id, domain, proof_hash, narration, firewall_result, word_count)
        VALUES (?,?,?,?,?,?)
    """, [agent_id, domain, proof_hash, narration, firewall_result,
          len(narration.split()) if narration else 0])
    con.close()

def get_streak(metric_key):
    con = duckdb.connect(DB_PATH)
    row = con.execute("SELECT unmapped_streak FROM sutra_streak WHERE metric_key=?", [metric_key]).fetchone()
    con.close()
    return row[0] if row else 0

def update_streak(metric_key, domain, z_score, increment=True):
    con = duckdb.connect(DB_PATH)
    existing = con.execute("SELECT unmapped_streak FROM sutra_streak WHERE metric_key=?", [metric_key]).fetchone()
    now = datetime.now(timezone.utc)
    if increment:
        new_streak = (existing[0] + 1) if existing else 1
        guna = "RAJAS" if new_streak >= 3 else "UNMAPPED"
    else:
        new_streak = 0
        guna = "SATTVA"
    if existing:
        con.execute("UPDATE sutra_streak SET unmapped_streak=?, last_seen_ts=?, last_z_score=?, guna_state=? WHERE metric_key=?",
                    [new_streak, now, z_score, guna, metric_key])
    else:
        con.execute("INSERT INTO sutra_streak (metric_key, domain, unmapped_streak, last_seen_ts, last_z_score, guna_state) VALUES (?,?,?,?,?,?)",
                    [metric_key, domain, new_streak, now, z_score, guna])
    con.close()
    return new_streak, guna

def query_memory(agent_id=None, domain=None, limit=20):
    con = duckdb.connect(DB_PATH)
    where = []
    params = []
    if agent_id: where.append("agent_id=?"); params.append(agent_id)
    if domain:   where.append("domain=?");   params.append(domain)
    clause = "WHERE " + " AND ".join(where) if where else ""
    rows = con.execute(f"SELECT * FROM agent_memory {clause} ORDER BY execution_ts DESC LIMIT {limit}", params).fetchall()
    con.close()
    return rows

if __name__ == "__main__":
    init_citta()
    # Test write
    append_memory("test_agent","public_health","weekly_deaths","US","1.0","abc","def","PASSED","SATTVA",urgency="HIGH",z_score=-4.31,severity="CRITICAL",anomalies_found=58,sutra_action="flag_reporting_lag",pancavayava_complete=True)
    rows = query_memory()
    print(f"agent_memory rows: {len(rows)}")
    # Test streak
    streak, guna = update_streak("public_health:weekly_deaths", "public_health", -4.31, increment=False)
    print(f"Streak reset: {streak}, Guna: {guna}")
