"""
OSIS – Database Initialization Layer (v3.0)
============================================
Domain-agnostic rewrite. Accepts any DatasetConfig object.
CDC is now just a default config — not hardcoded logic.

SOVEREIGNTY RULE: Only this module writes to canonical_metrics.
All other agents use read_only=True connections.
"""

import duckdb
from dataset_config import DatasetConfig, get_default_config
from schema_adapter import load_dataframe

DB_NAME = "osis_strategic_archives.db"


def initialize_osis_db(config: DatasetConfig = None):
    """
    Initialize the OSIS archive for any dataset.
    If no config provided, uses CDC mortality (default).
    """
    if config is None:
        config = get_default_config()

    print(f"\n{'='*55}")
    print(f"  🏛️  OSIS Strategic Archive — Initialization")
    print(f"{'='*55}\n")
    print(f"  Domain  : {config.domain}")
    print(f"  Metric  : {config.metric_name}")
    print(f"  Source  : {config.source_label}\n")

    con = duckdb.connect(DB_NAME)

    try:
        # ── STEP 1: Load raw data ─────────────────────────────────────────────
        print("📡 Step 1: Ingesting raw data...")

        df = load_dataframe(config.source_path, config.source_type)

        raw_count = len(df)
        col_names = list(df.columns)

        print(f"   ✅ Raw records loaded   : {raw_count:,}")
        print(f"   📊 Columns detected     : {len(col_names)}")
        print(f"   Fields (first 8)        : {col_names[:8]}\n")

        # ── STEP 2: Validate config columns exist ────────────────────────────
        print("🔍 Step 2: Validating column mapping...")

        missing = []
        if config.date_col not in df.columns:
            # Try case-insensitive match
            match = _find_column(col_names, [config.date_col])
            if match:
                config.date_col = match
            else:
                missing.append(f"date_col='{config.date_col}'")

        if config.value_col not in df.columns:
            match = _find_column(col_names, [config.value_col])
            if match:
                config.value_col = match
            else:
                missing.append(f"value_col='{config.value_col}'")

        if config.entity_col and config.entity_col not in df.columns:
            match = _find_column(col_names, [config.entity_col])
            if match:
                config.entity_col = match
            else:
                print(f"   ⚠️  entity_col='{config.entity_col}' not found — proceeding without entity filter")
                config.entity_col = None

        if missing:
            raise ValueError(f"Required columns not found: {missing}. Available: {col_names}")

        print(f"   Date column   → {config.date_col}")
        print(f"   Value column  → {config.value_col}")
        print(f"   Entity column → {config.entity_col or 'None (no entity filter)'}\n")

        # ── STEP 3: Store raw data in DuckDB ──────────────────────────────────
        print("🗄️  Step 3: Archiving raw data...")
        con.execute("DROP TABLE IF EXISTS raw_source_data;")
        con.register("_raw_df", df)
        con.execute("CREATE TABLE raw_source_data AS SELECT * FROM _raw_df;")
        con.unregister("_raw_df")
        print(f"   ✅ raw_source_data: {raw_count:,} rows archived\n")

        # ── STEP 4: Project into canonical_metrics ────────────────────────────
        print("🏗️  Step 4: Projecting into canonical_metrics...")

        con.execute("DROP TABLE IF EXISTS canonical_metrics;")
        con.execute("""
            CREATE TABLE canonical_metrics (
                domain        VARCHAR,
                metric_name   VARCHAR,
                time_period   DATE,
                metric_value  DOUBLE,
                state         VARCHAR,
                source_table  VARCHAR,
                schema_version VARCHAR DEFAULT '1.0',
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Build INSERT dynamically from config
        entity_expr = f'"{config.entity_col}"' if config.entity_col \
                      else f"'{config.entity_filter}'"

        con.execute(f"""
            INSERT INTO canonical_metrics
                (domain, metric_name, time_period, metric_value, state, source_table)
            SELECT
                '{config.domain}'       AS domain,
                '{config.metric_name}'  AS metric_name,
                TRY_CAST("{config.date_col}"  AS DATE)   AS time_period,
                TRY_CAST("{config.value_col}" AS DOUBLE) AS metric_value,
                {entity_expr}           AS state,
                'raw_source_data'       AS source_table
            FROM raw_source_data
            WHERE TRY_CAST("{config.date_col}"  AS DATE)   IS NOT NULL
              AND TRY_CAST("{config.value_col}" AS DOUBLE) IS NOT NULL
              AND TRY_CAST("{config.value_col}" AS DOUBLE) > 0;
        """)

        n = con.execute("SELECT COUNT(*) FROM canonical_metrics").fetchone()[0]
        print(f"   ✅ {config.metric_name} : {n:,} rows\n")

        # ── STEP 5: Verification ──────────────────────────────────────────────
        print("📋 Step 5: Verification")
        print(f"   Total canonical rows : {n:,}")

        date_range = con.execute(
            "SELECT MIN(time_period), MAX(time_period) FROM canonical_metrics"
        ).fetchone()
        print(f"   Date range           : {date_range[0]} → {date_range[1]}")

        if config.entity_col:
            entity_count = con.execute(
                "SELECT COUNT(DISTINCT state) FROM canonical_metrics"
            ).fetchone()[0]
            print(f"   Entities             : {entity_count:,} unique")

        print(f"\n✅ OSIS Strategic Archive ready: {DB_NAME}")
        print(f"   Schema version: {config.schema_version}\n")

        return config  # Return config so main.py can pass it downstream

    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None
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
    from dataset_config import CDC_MORTALITY
    initialize_osis_db(CDC_MORTALITY)