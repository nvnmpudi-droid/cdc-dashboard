"""
OSIS – Schema Adapter (v1.0)
==============================
Profiles any dataset (CSV, JSON, Excel, API) and returns a DatasetConfig.
This is Agent 1 — the Data Adapter layer.

Design:
  - Auto-detects date, numeric metric, and entity columns
  - Returns a DatasetConfig ready for all downstream agents
  - Never modifies canonical_metrics directly (that is database_init's job)
  - Para layer: treats all input as immutable during profiling

SOVEREIGNTY RULE: This module only reads source data and produces config.
It never writes to DuckDB or modifies any agent output.
"""

import re
import pandas as pd
from pathlib import Path
from typing import Optional
from dataset_config import DatasetConfig


# ── Column name heuristics ────────────────────────────────────────────────────
DATE_CANDIDATES = [
    "date", "week_ending_date", "weekendingdate", "end_week", "time_period",
    "week", "period", "timestamp", "report_date", "observation_date",
    "admission_date", "discharge_date", "encounter_date"
]

ENTITY_CANDIDATES = [
    "state", "jurisdiction", "jurisdiction_of_occurrence", "region",
    "county", "facility", "hospital", "location", "site", "department",
    "organization", "entity", "group"
]

# Columns to skip — these are never the primary metric
SKIP_COLS = [
    "year", "month", "week", "mmwryear", "mmwrweek", "data_as_of",
    "start_week", "end_week", "flag", "suppress", "note", "id",
    "fips", "code", "icd"
]


def load_dataframe(source_path: str, source_type: str = "auto") -> pd.DataFrame:
    """Load a dataset from file path or URL into a DataFrame."""

    path = str(source_path)

    # Auto-detect type
    if source_type == "auto":
        if path.startswith("http"):
            if ".json" in path or "json" in path.lower():
                source_type = "api"
            else:
                source_type = "api"
        elif path.endswith(".csv"):
            source_type = "csv"
        elif path.endswith(".xlsx") or path.endswith(".xls"):
            source_type = "excel"
        elif path.endswith(".json"):
            source_type = "json"
        else:
            source_type = "csv"  # default

    if source_type in ("api", "json") and path.startswith("http"):
        import requests
        resp = requests.get(path, timeout=30)
        resp.raise_for_status()
        df = pd.DataFrame(resp.json())
    elif source_type == "csv":
        df = pd.read_csv(path)
    elif source_type == "excel":
        df = pd.read_excel(path)
    elif source_type == "json":
        df = pd.read_json(path)
    else:
        df = pd.read_csv(path)

    return df


def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Find the most likely date/time column."""
    cols_lower = {c.lower(): c for c in df.columns}

    # First: check known candidates
    for cand in DATE_CANDIDATES:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]

    # Second: try to parse columns as dates
    for col in df.columns:
        if col.lower() in [s.lower() for s in SKIP_COLS]:
            continue
        sample = df[col].dropna().head(10)
        try:
            parsed = pd.to_datetime(sample, errors="coerce")
            if parsed.notna().sum() >= 8:
                return col
        except Exception:
            continue

    return None


def detect_entity_column(df: pd.DataFrame) -> Optional[str]:
    """Find the most likely entity/jurisdiction column."""
    cols_lower = {c.lower(): c for c in df.columns}

    for cand in ENTITY_CANDIDATES:
        if cand.lower() in cols_lower:
            col = cols_lower[cand.lower()]
            # Verify it's categorical (low cardinality string)
            if df[col].dtype == object:
                n_unique = df[col].nunique()
                if 2 <= n_unique <= 200:
                    return col

    # Fallback: find any string column with low cardinality
    for col in df.columns:
        if df[col].dtype == object:
            n_unique = df[col].nunique()
            if 2 <= n_unique <= 100:
                return col

    return None


def detect_metric_columns(df: pd.DataFrame, date_col: str,
                           entity_col: Optional[str]) -> list[str]:
    """Find all numeric columns that could be metrics."""
    skip = set()
    if date_col:
        skip.add(date_col.lower())
    if entity_col:
        skip.add(entity_col.lower())
    for s in SKIP_COLS:
        skip.add(s.lower())

    candidates = []
    for col in df.columns:
        if col.lower() in skip:
            continue
        # Try numeric conversion
        numeric = pd.to_numeric(df[col], errors="coerce")
        pct_valid = numeric.notna().mean()
        if pct_valid >= 0.5:
            max_val = numeric.max()
            # Skip columns that look like IDs or flags (all small integers)
            if max_val > 10:
                candidates.append(col)

    return candidates


def score_metric_column(df: pd.DataFrame, col: str) -> float:
    """Score a metric column — higher is better primary metric candidate."""
    numeric = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(numeric) < 10:
        return 0.0

    score = 0.0
    # More complete data = better
    score += numeric.notna().mean() * 2.0
    # Higher variance = more interesting
    cv = numeric.std() / (numeric.mean() + 1e-9)
    score += min(cv, 1.0)
    # Larger values tend to be primary metrics vs derived flags
    if numeric.max() > 1000:
        score += 0.5

    return score


def get_entity_filter(df: pd.DataFrame, entity_col: str) -> str:
    """Pick the best entity to analyze by default — largest count."""
    counts = df[entity_col].value_counts()
    return counts.index[0]


def profile_dataset(
    source_path: str,
    source_type: str = "auto",
    domain: str = "general",
    metric_hint: Optional[str] = None,
    entity_hint: Optional[str] = None,
) -> dict:
    """
    Profile a dataset and return column recommendations.
    Does NOT return a DatasetConfig — caller confirms and builds one.

    Returns:
        {
          "df": DataFrame,
          "date_col": str,
          "entity_col": str | None,
          "metric_columns": [str, ...],
          "recommended_metric": str,
          "available_entities": [str, ...],
          "recommended_entity": str | None,
          "row_count": int,
          "col_count": int
        }
    """
    df = load_dataframe(source_path, source_type)

    date_col   = detect_date_column(df)
    entity_col = entity_hint or detect_entity_column(df)
    metrics    = detect_metric_columns(df, date_col, entity_col)

    # Score and rank metric columns
    scores = {col: score_metric_column(df, col) for col in metrics}
    ranked = sorted(scores, key=scores.get, reverse=True)

    recommended_metric = metric_hint or (ranked[0] if ranked else None)

    # Available entities
    available_entities = []
    recommended_entity = None
    if entity_col and entity_col in df.columns:
        available_entities = df[entity_col].dropna().unique().tolist()[:50]
        recommended_entity = get_entity_filter(df, entity_col)

    return {
        "df": df,
        "date_col": date_col,
        "entity_col": entity_col,
        "metric_columns": ranked,
        "recommended_metric": recommended_metric,
        "available_entities": sorted(available_entities),
        "recommended_entity": recommended_entity,
        "row_count": len(df),
        "col_count": len(df.columns),
        "source_path": source_path,
        "source_type": source_type,
        "domain": domain
    }


def build_config_from_profile(
    profile: dict,
    metric_name_label: str,
    entity_filter: str,
    domain: str,
    source_label: str,
    rolling_window: int = 4,
    forecast_horizon: int = 4,
    lag_periods: int = 4,
) -> DatasetConfig:
    """
    Build a DatasetConfig from a confirmed profile.
    Call this after the user confirms column selections.
    """
    return DatasetConfig(
        domain=domain,
        metric_name=_slugify(metric_name_label),
        source_label=source_label,
        date_col=profile["date_col"],
        value_col=profile["recommended_metric"],
        entity_col=profile["entity_col"],
        entity_filter=entity_filter,
        source_type=profile["source_type"],
        source_path=profile["source_path"],
        rolling_window=rolling_window,
        forecast_horizon=forecast_horizon,
        lag_periods=lag_periods,
    )


def _slugify(text: str) -> str:
    """Convert display name to snake_case metric key."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text


# ── CLI usage ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "https://data.cdc.gov/resource/muzy-jte6.json?$limit=1000"

    print(f"\nProfiling: {path}\n")
    profile = profile_dataset(path)

    print(f"Rows         : {profile['row_count']:,}")
    print(f"Columns      : {profile['col_count']}")
    print(f"Date column  : {profile['date_col']}")
    print(f"Entity col   : {profile['entity_col']}")
    print(f"Top metrics  : {profile['metric_columns'][:5]}")
    print(f"Recommended  : {profile['recommended_metric']}")
    print(f"Entities     : {profile['available_entities'][:5]}")