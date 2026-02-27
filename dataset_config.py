from dataclasses import dataclass
from typing import Optional

@dataclass
class DatasetConfig:
    domain: str
    metric_name: str
    source_label: str
    date_col: str
    value_col: str
    entity_col: Optional[str]
    entity_filter: str
    source_type: str
    source_path: str
    rolling_window: int = 4
    forecast_horizon: int = 4
    lag_periods: int = 4
    anomaly_threshold: float = 2.0
    critical_threshold: float = 3.0
    schema_version: str = "1.0"

    def to_dict(self):
        return self.__dict__

CDC_MORTALITY = DatasetConfig(
    domain="public_health",
    metric_name="weekly_deaths_all_cause",
    source_label="CDC NVSS Weekly Mortality",
    date_col="week_ending_date",
    value_col="all_cause",
    entity_col="jurisdiction_of_occurrence",
    entity_filter="United States",
    source_type="api",
    source_path="https://data.cdc.gov/resource/muzy-jte6.json?$limit=10000",
)

def get_default_config():
    return CDC_MORTALITY
HOSPITAL_ADMISSIONS = DatasetConfig(
    domain="hospital_ops",
    metric_name="weekly_admissions",
    source_label="Hospital Admissions (Synthetic Demo)",
    date_col="week_ending",
    value_col="weekly_admissions",
    entity_col="service_line",
    entity_filter="medical",
    source_type="csv",
    source_path="data/hospital_admissions.csv",
    schema_version="1.0",
)
