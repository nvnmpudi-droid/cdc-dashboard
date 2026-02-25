"""
OSIS – Database Initialization Layer (v2.0)
============================================
What this does:
  1. Creates raw CDC mirror table (cdc_mortality) — exactly as before
  2. Projects it into canonical_metrics — the standardized contract
     that every downstream agent (LogicAgent, Chanakya, etc.) reads from
  3. Verifies both tables and reports ingestion health

Why canonical_metrics matters:
  The LogicAgent doesn't know or care what CDC calls their columns.
  It only speaks:  domain | metric_name | time_period | metric_value
  This table is that translation layer.
"""

import duckdb

DB_NAME = "osis_strategic_archives.db"
CDC_API_URL = "https://data.cdc.gov/resource/muzy-jte6.json?$limit=10000"


def initialize_osis_db():
    print(f"\n{'='*55}")
    print(f"  🏛️  OSIS Strategic Archive — Initialization")
    print(f"{'='*55}\n")

    con = duckdb.connect(DB_NAME)

    try:
        # ── STEP 1: Raw Ingest (your original logic, kept intact) ────────────
        print("📡 Step 1: Ingesting raw CDC data...")
        con.execute(f"""
            CREATE OR REPLACE TABLE cdc_mortality AS
            SELECT * FROM read_json_auto('{CDC_API_URL}');
        """)

        raw_count = con.execute("SELECT COUNT(*) FROM cdc_mortality").fetchone()[0]
        columns = con.execute("DESCRIBE cdc_mortality").fetchall()
        col_names = [col[0] for col in columns]

        print(f"   ✅ Raw records archived : {raw_count:,}")
        print(f"   📊 Columns detected     : {len(col_names)}")
        print(f"   Fields (first 8)        : {col_names[:8]}\n")

        # ── STEP 2: Detect which columns hold what we need ───────────────────
        # CDC column names shift between API versions — we handle both
        print("🔍 Step 2: Detecting schema columns...")

        # Date column — could be either of these
        date_col = _find_column(col_names, ["week_ending_date", "weekendingdate", "end_week", "date"])
        # All-cause deaths
        all_cause_col = _find_column(col_names, ["all_cause", "allcause", "all_deaths", "number_of_deaths"])
        # COVID deaths
        covid_col = _find_column(col_names, ["covid_19", "covid19", "covid_19_deaths", "covid"])
        # State/jurisdiction
        state_col = _find_column(col_names, ["jurisdiction_of_occurrence", "state", "jurisdiction"])

        print(f"   Date column      → {date_col or 'NOT FOUND'}")
        print(f"   All-cause column → {all_cause_col or 'NOT FOUND'}")
        print(f"   COVID column     → {covid_col or 'NOT FOUND'}")
        print(f"   State column     → {state_col or 'NOT FOUND'}\n")

        if not date_col:
            raise ValueError(
                "Cannot find a date column in CDC data. "
                f"Available columns: {col_names}"
            )

        # ── STEP 3: Build canonical_metrics ──────────────────────────────────
        # Each metric gets its own rows with a clear metric_name label.
        # LogicAgent queries: WHERE domain='public_health' AND metric_name='weekly_deaths_all_cause'
        print("🏗️  Step 3: Projecting into canonical_metrics table...")

        con.execute("DROP TABLE IF EXISTS canonical_metrics;")
        con.execute("""
            CREATE TABLE canonical_metrics (
                domain        VARCHAR,
                metric_name   VARCHAR,
                time_period   DATE,
                metric_value  DOUBLE,
                state         VARCHAR,
                source_table  VARCHAR,
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        total_inserted = 0

        # -- Metric A: All-cause weekly deaths (national) ---------------------
        if all_cause_col and state_col:
            con.execute(f"""
                INSERT INTO canonical_metrics (domain, metric_name, time_period, metric_value, state, source_table)
                SELECT
                    'public_health'            AS domain,
                    'weekly_deaths_all_cause'  AS metric_name,
                    TRY_CAST("{date_col}" AS DATE) AS time_period,
                    TRY_CAST("{all_cause_col}" AS DOUBLE) AS metric_value,
                    "{state_col}"              AS state,
                    'cdc_mortality'            AS source_table
                FROM cdc_mortality
                WHERE TRY_CAST("{date_col}" AS DATE) IS NOT NULL
                  AND TRY_CAST("{all_cause_col}" AS DOUBLE) IS NOT NULL
                  AND TRY_CAST("{all_cause_col}" AS DOUBLE) > 0;
            """)
            n = con.execute(
                "SELECT COUNT(*) FROM canonical_metrics WHERE metric_name='weekly_deaths_all_cause'"
            ).fetchone()[0]
            total_inserted += n
            print(f"   ✅ weekly_deaths_all_cause : {n:,} rows")

        elif all_cause_col:
            # No state column — insert without state filter
            con.execute(f"""
                INSERT INTO canonical_metrics (domain, metric_name, time_period, metric_value, state, source_table)
                SELECT
                    'public_health', 'weekly_deaths_all_cause',
                    TRY_CAST("{date_col}" AS DATE),
                    TRY_CAST("{all_cause_col}" AS DOUBLE),
                    'United States', 'cdc_mortality'
                FROM cdc_mortality
                WHERE TRY_CAST("{date_col}" AS DATE) IS NOT NULL
                  AND TRY_CAST("{all_cause_col}" AS DOUBLE) IS NOT NULL
                  AND TRY_CAST("{all_cause_col}" AS DOUBLE) > 0;
            """)
            n = con.execute(
                "SELECT COUNT(*) FROM canonical_metrics WHERE metric_name='weekly_deaths_all_cause'"
            ).fetchone()[0]
            total_inserted += n
            print(f"   ✅ weekly_deaths_all_cause : {n:,} rows")
        else:
            print("   ⚠️  Skipped weekly_deaths_all_cause — column not found")

        # -- Metric B: COVID-19 weekly deaths ---------------------------------
        if covid_col:
            con.execute(f"""
                INSERT INTO canonical_metrics (domain, metric_name, time_period, metric_value, state, source_table)
                SELECT
                    'public_health'         AS domain,
                    'weekly_deaths_covid19' AS metric_name,
                    TRY_CAST("{date_col}" AS DATE) AS time_period,
                    TRY_CAST("{covid_col}" AS DOUBLE) AS metric_value,
                    COALESCE("{state_col if state_col else "'United States'"}") AS state,
                    'cdc_mortality' AS source_table
                FROM cdc_mortality
                WHERE TRY_CAST("{date_col}" AS DATE) IS NOT NULL
                  AND TRY_CAST("{covid_col}" AS DOUBLE) IS NOT NULL
                  AND TRY_CAST("{covid_col}" AS DOUBLE) > 0;
            """)
            n = con.execute(
                "SELECT COUNT(*) FROM canonical_metrics WHERE metric_name='weekly_deaths_covid19'"
            ).fetchone()[0]
            total_inserted += n
            print(f"   ✅ weekly_deaths_covid19   : {n:,} rows")
        else:
            print("   ⚠️  Skipped weekly_deaths_covid19 — column not found")

        # ── STEP 4: Verification ─────────────────────────────────────────────
        print(f"\n📋 Step 4: Verification")
        print(f"   Total canonical rows    : {total_inserted:,}")

        date_range = con.execute("""
            SELECT MIN(time_period), MAX(time_period) FROM canonical_metrics
        """).fetchone()
        print(f"   Date range              : {date_range[0]} → {date_range[1]}")

        metrics = con.execute("""
            SELECT metric_name, COUNT(*) as n
            FROM canonical_metrics
            GROUP BY metric_name
            ORDER BY metric_name
        """).fetchall()
        print(f"   Metrics available:")
        for m in metrics:
            print(f"     - {m[0]:<35} {m[1]:>6} rows")

        print(f"\n✅ OSIS Strategic Archive ready: {DB_NAME}")
        print(f"   LogicAgent can now query canonical_metrics.\n")

    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        con.close()


def _find_column(available: list, candidates: list) -> str | None:
    """Case-insensitive column name resolver."""
    lower_available = {c.lower(): c for c in available}
    for candidate in candidates:
        if candidate.lower() in lower_available:
            return lower_available[candidate.lower()]
    return None


if __name__ == "__main__":
    initialize_osis_db()