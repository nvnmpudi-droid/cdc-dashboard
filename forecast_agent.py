import json
import warnings
import duckdb
import pandas as pd
from datetime import datetime, timezone
from dataset_config import DatasetConfig, get_default_config

warnings.filterwarnings("ignore")
DB_PATH = "osis_strategic_archives.db"
OUTPUT_FILE = "forecast_output.json"

def load_data(config):
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("SELECT time_period, metric_value FROM canonical_metrics WHERE state=? AND metric_name=? AND domain=? ORDER BY time_period ASC",
        [config.entity_filter, config.metric_name, config.domain]).fetchdf()
    con.close()
    df["time_period"] = pd.to_datetime(df["time_period"])
    return df.dropna(subset=["metric_value"])

def run_forecast_agent(config=None):
    if config is None:
        config = get_default_config()
    print("="*55)
    print("  OSIS Forecast Agent -- Prophet v2.0")
    print("="*55)
    print(f"  Domain : {config.domain}")
    print(f"  Metric : {config.metric_name}")
    print(f"  Entity : {config.entity_filter}")
    df = load_data(config)
    print(f"  Loaded {len(df)} records")
    try:
        from prophet import Prophet
    except ImportError:
        print("  Forecast Agent: Prophet not available — skipping forecast")
        return {"status": "skipped", "message": "Prophet not installed", "forecast": [], "trend": {"direction": "unknown", "pct_change": 0.0}}
    prophet_df = df.rename(columns={"time_period": "ds", "metric_value": "y"})
    prophet_df = prophet_df.iloc[:-config.lag_periods].copy()
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False,
        daily_seasonality=False, seasonality_mode="additive",
        interval_width=0.95, changepoint_prior_scale=0.05)
    model.fit(prophet_df)
    future = model.make_future_dataframe(periods=config.forecast_horizon, freq="W")
    forecast = model.predict(future)
    fcast_rows = forecast.tail(config.forecast_horizon)[["ds","yhat","yhat_lower","yhat_upper"]].reset_index(drop=True)
    last_actual = df.iloc[-(config.lag_periods+1)]
    first_f = float(fcast_rows.iloc[0]["yhat"])
    last_f  = float(fcast_rows.iloc[-1]["yhat"])
    trend   = "increasing" if last_f > first_f else "decreasing"
    pct     = ((last_f - first_f) / (first_f + 1e-9)) * 100
    forecasts = [{"period_ending": str(r["ds"])[:10], "forecast": round(float(r["yhat"])),
        "lower_95": round(float(r["yhat_lower"])), "upper_95": round(float(r["yhat_upper"]))}
        for _,r in fcast_rows.iterrows()]
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": config.schema_version,
        "status": "success", "model": "prophet",
        "domain": config.domain, "metric_name": config.metric_name,
        "state": config.entity_filter,
        "horizon_periods": config.forecast_horizon,
        "last_known": {"date": str(last_actual["time_period"])[:10], "value": int(last_actual["metric_value"])},
        "forecast": forecasts,
        "trend": {"direction": trend, "pct_change": round(pct,2), "start_value": round(first_f), "end_value": round(last_f)},
        "tarka_note": f"Prophet forecast with 95% CI. Final {config.lag_periods} periods excluded for reporting lag."
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Trend: {trend} ({pct:+.1f}%)")
    for fc in forecasts:
        print(f"  {fc['period_ending']}  {fc['forecast']:>8,}  [{fc['lower_95']:,} - {fc['upper_95']:,}]")
    print(f"Forecast saved -> {OUTPUT_FILE}")
    return output
