"""
Pydantic v2 response models for all API endpoints.

These models:
  - Define the exact JSON shapes returned to the frontend.
  - Drive the auto-generated OpenAPI / Swagger documentation.
  - Validate data before serialisation, surfacing bugs early.

All datetime fields are serialised as ISO-8601 UTC strings (Z suffix).
All power values are in MW (megawatts).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


# ------------------------------------------------------------------ #
# Shared serialiser helpers
# ------------------------------------------------------------------ #

def _fmt_dt(dt: datetime) -> str:
    """Serialise a datetime as ISO-8601 UTC with Z suffix."""
    if dt.tzinfo is None:
        # Should never happen — all datetimes in this app are tz-aware.
        return dt.isoformat() + "Z"
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

class HealthResponse(BaseModel):
    status: str = Field(description="'ok' or 'degraded'")
    cache_loaded: bool = Field(description="True when both datasets are in memory")
    actuals_rows: Optional[int] = Field(None, description="Number of FUELHH rows cached")
    forecast_rows: Optional[int] = Field(None, description="Number of WINDFOR rows cached (after hindcast removal)")
    data_period: Optional[str] = Field(None, description="Settlement date range of actuals")
    error: Optional[str] = Field(None, description="Error message if cache failed to load")

    model_config = {"json_schema_extra": {
        "example": {
            "status": "ok",
            "cache_loaded": True,
            "actuals_rows": 1488,
            "forecast_rows": 16239,
            "data_period": "2026-01-01 to 2026-01-31",
            "error": None,
        }
    }}


# ------------------------------------------------------------------ #
# Data status
# ------------------------------------------------------------------ #

class DataStatusResponse(BaseModel):
    cache_loaded: bool
    actuals_rows: Optional[int] = None
    forecast_rows: Optional[int] = None
    forecast_vintages: Optional[int] = Field(
        None, description="Total (publish_time, start_time) pairs retained"
    )
    unique_delivery_hours: Optional[int] = Field(
        None, description="Distinct delivery hours covered by forecasts"
    )
    actuals_date_from: Optional[str] = None
    actuals_date_to: Optional[str] = None
    forecasts_publish_from: Optional[str] = None
    forecasts_publish_to: Optional[str] = None
    missing_actual_periods: Optional[int] = Field(
        None, description="Settlement periods absent from FUELHH response"
    )
    negative_forecast_rows_clamped: Optional[int] = Field(
        None, description="Number of WINDFOR rows where generation was negative and clamped to 0"
    )


# ------------------------------------------------------------------ #
# Actuals
# ------------------------------------------------------------------ #

class ActualRecord(BaseModel):
    """One 30-minute FUELHH settlement period."""
    start_time: datetime
    settlement_date: date
    settlement_period: int = Field(ge=1, le=48)
    generation_mw: float = Field(description="Actual wind output (MW)")
    publish_time: datetime
    is_on_hour: bool = Field(description="True when start_time is on the hour (HH:00:00Z)")

    @field_serializer("start_time", "publish_time")
    def serialise_dt(self, v: datetime) -> str:
        return _fmt_dt(v)

    @field_serializer("settlement_date")
    def serialise_date(self, v: date) -> str:
        return v.isoformat()


class ActualsResponse(BaseModel):
    total_rows: int
    on_hour_rows: int
    records: list[ActualRecord]


# ------------------------------------------------------------------ #
# Forecasts / vintages
# ------------------------------------------------------------------ #

class ForecastRecord(BaseModel):
    """One WINDFOR publish-time / delivery-hour pair (a vintage)."""
    publish_time: datetime
    start_time: datetime
    generation_mw: float = Field(description="Forecast wind output (MW)")
    lead_hours: float = Field(description="Hours from publication to delivery")

    @field_serializer("publish_time", "start_time")
    def serialise_dt(self, v: datetime) -> str:
        return _fmt_dt(v)


class ForecastsResponse(BaseModel):
    total_vintages: int
    unique_delivery_hours: int
    records: list[ForecastRecord]


class ForecastVintagesResponse(BaseModel):
    """All vintages for one specific delivery hour."""
    delivery_hour: str = Field(description="ISO-8601 UTC delivery hour")
    n_vintages: int
    vintages: list[ForecastRecord]


class LatestForecastRecord(BaseModel):
    """The most-recently-published forecast for a delivery hour (no cutoff applied)."""
    start_time: datetime
    generation_mw: float
    publish_time: datetime
    lead_hours: float

    @field_serializer("start_time", "publish_time")
    def serialise_dt(self, v: datetime) -> str:
        return _fmt_dt(v)


class LatestForecastsResponse(BaseModel):
    cutoff_note: str = Field(
        description="Reminder: these are the latest available vintages, not day-ahead decision forecasts"
    )
    records: list[LatestForecastRecord]


# ------------------------------------------------------------------ #
# Accuracy metrics
# ------------------------------------------------------------------ #

class SummaryMetrics(BaseModel):
    period_label: str
    n_matched_intervals: int = Field(description="Hours with both forecast and actual")
    n_total_intervals: int = Field(description="Total delivery hours in the period")
    coverage_pct: float = Field(description="n_matched / n_total × 100")
    mae_mw: float = Field(description="Mean Absolute Error (MW) = mean(|forecast − actual|)")
    rmse_mw: float = Field(description="Root Mean Square Error (MW) = sqrt(mean((forecast − actual)²))")
    mbe_mw: float = Field(
        description=(
            "Mean Bias Error (MW) = mean(forecast − actual). "
            "Positive → forecast overestimated wind. "
            "Negative → underestimated wind. "
            "NOTE: does not indicate electricity procurement quantity."
        )
    )
    mape_pct: Optional[float] = Field(
        None,
        description=(
            "Mean Absolute Percentage Error (%) = mean(|error/actual|)×100. "
            "Computed over non-zero actual intervals only. "
            "Null when all actuals are zero."
        ),
    )
    mape_zero_exclusions: int = Field(
        default=0,
        description="Number of intervals excluded from MAPE due to zero actual generation.",
    )
    nmae_pct: float = Field(description="Normalised MAE = MAE / mean(actual) × 100 (%)")
    mean_actual_mw: float
    mean_forecast_mw: float
    mean_lead_hours: float
    over_forecast_count: int = Field(
        default=0, description="Intervals where forecast > actual (error_mw > 0)"
    )
    under_forecast_count: int = Field(
        default=0, description="Intervals where forecast < actual (error_mw < 0)"
    )
    over_forecast_pct: float = Field(
        default=0.0, description="over_forecast_count / n_matched × 100"
    )
    under_forecast_pct: float = Field(
        default=0.0, description="under_forecast_count / n_matched × 100"
    )
    max_over_forecast_mw: float = Field(
        default=0.0, description="Largest single overforecast error (MW)"
    )
    max_under_forecast_mw: float = Field(
        default=0.0, description="Largest single underforecast magnitude (MW)"
    )


# ------------------------------------------------------------------ #
# Timeseries point (joined forecast + actual)
# ------------------------------------------------------------------ #

class TimeseriesPoint(BaseModel):
    start_time: datetime
    settlement_date: date
    settlement_period: int
    forecast_mw: float
    actual_mw: float
    forecast_publish_time: datetime
    lead_hours: float
    error_mw: float = Field(description="forecast − actual (MW)")
    abs_error_mw: float
    pct_error: Optional[float] = Field(None, description="(forecast − actual) / actual × 100")

    @field_serializer("start_time", "forecast_publish_time")
    def serialise_dt(self, v: datetime) -> str:
        return _fmt_dt(v)

    @field_serializer("settlement_date")
    def serialise_date(self, v: date) -> str:
        return v.isoformat()


# ------------------------------------------------------------------ #
# Daily metrics
# ------------------------------------------------------------------ #

class DailyMetrics(BaseModel):
    settlement_date: date
    n_intervals: int
    mean_forecast_mw: float
    mean_actual_mw: float
    mae_mw: float
    mbe_mw: float
    rmse_mw: float

    @field_serializer("settlement_date")
    def serialise_date(self, v: date) -> str:
        return v.isoformat()


# ------------------------------------------------------------------ #
# Horizon analysis
# ------------------------------------------------------------------ #

class HorizonBucket(BaseModel):
    bucket_label: str = Field(description="e.g. '24–30h'")
    lead_hours_min: float
    lead_hours_max: float
    n_intervals: int
    mae_mw: float
    mbe_mw: float
    rmse_mw: float


# ------------------------------------------------------------------ #
# Error distribution
# ------------------------------------------------------------------ #

class ErrorBin(BaseModel):
    bin_label: str = Field(description="e.g. '-2000 to -1500'")
    bin_min_mw: float
    bin_max_mw: float
    count: int
    pct_of_total: float


class ErrorDistributionResponse(BaseModel):
    cutoff_hour_utc: int
    total_intervals: int
    bins: list[ErrorBin]
    mean_error_mw: float
    std_error_mw: float


# ------------------------------------------------------------------ #
# Dashboard summary (composite)
# ------------------------------------------------------------------ #

class AnalysisParameters(BaseModel):
    start_date: str
    end_date: str
    cutoff_hour_utc: int


class DashboardSummaryResponse(BaseModel):
    parameters: AnalysisParameters
    summary: SummaryMetrics
    timeseries: list[TimeseriesPoint]
    daily: list[DailyMetrics]
    horizon: list[HorizonBucket]
    assumption_note: str = Field(
        description=(
            "ASSUMPTION A1: Day-ahead cutoff is set to 09:00 UTC on D-1 by default. "
            "The GB EPEX SPOT auction closes ~09:20–09:50 UK local time (GMT in January). "
            "This is an analytical proxy, not a confirmed client trading rule."
        )
    )


# ------------------------------------------------------------------ #
# Analytics accuracy endpoint
# ------------------------------------------------------------------ #

class AccuracyResponse(BaseModel):
    parameters: AnalysisParameters
    summary: SummaryMetrics
    assumption_note: str


# ------------------------------------------------------------------ #
# Analytics daily endpoint
# ------------------------------------------------------------------ #

class DailyAnalyticsResponse(BaseModel):
    parameters: AnalysisParameters
    daily: list[DailyMetrics]


# ------------------------------------------------------------------ #
# Analytics errors endpoint
# ------------------------------------------------------------------ #

class ErrorsResponse(BaseModel):
    parameters: AnalysisParameters
    timeseries: list[TimeseriesPoint]
    distribution: ErrorDistributionResponse


# ------------------------------------------------------------------ #
# Day detail (chart/day/{date})
# ------------------------------------------------------------------ #

class DayDetailInterval(BaseModel):
    """
    One delivery hour on a specific day.
    Includes both on-the-hour and half-hour actuals for chart display.
    Only on_hour actuals are used in metric calculations (Assumption A2).
    """
    hour_utc: str = Field(description="e.g. '00:00', '01:00'")
    start_time: datetime
    settlement_period_on_hour: int = Field(description="SP for HH:00 (odd: 1,3,5…47)")
    forecast_mw: Optional[float] = None
    actual_mw_on_hour: Optional[float] = Field(None, description="HH:00 actual — used in metrics")
    actual_mw_half_hour: Optional[float] = Field(None, description="HH:30 actual — display only")
    error_mw: Optional[float] = None
    forecast_publish_time: Optional[datetime] = None
    lead_hours: Optional[float] = None

    @field_serializer("start_time")
    def serialise_dt(self, v: datetime) -> str:
        return _fmt_dt(v)

    @field_serializer("forecast_publish_time")
    def serialise_opt_dt(self, v: Optional[datetime]) -> Optional[str]:
        return _fmt_dt(v) if v is not None else None


# ------------------------------------------------------------------ #
# Time-of-day analysis
# ------------------------------------------------------------------ #

class TimeOfDayMetrics(BaseModel):
    hour_of_day: int = Field(ge=0, le=23)
    hour_label: str = Field(description="e.g. '09:00'")
    n_intervals: int
    mean_forecast_mw: float
    mean_actual_mw: float
    mae_mw: float
    mbe_mw: float
    rmse_mw: float


class TimeOfDayResponse(BaseModel):
    parameters: AnalysisParameters
    hours: list[TimeOfDayMetrics]
    note: str = Field(
        default=(
            "Metrics are computed over all January 2026 days for each UTC hour. "
            "n_intervals = number of days that hour appears in matched data (max 31)."
        )
    )


# ------------------------------------------------------------------ #
# Forecast revision analysis
# ------------------------------------------------------------------ #

class RevisionRecord(BaseModel):
    start_time: str
    first_forecast_mw: Optional[float]
    first_publish_time: Optional[str]
    decision_forecast_mw: float
    decision_publish_time: str
    revision_mw: Optional[float] = Field(
        None,
        description=(
            "decision_forecast − first_forecast. "
            "Positive = forecast was revised upward between first publication and decision time."
        ),
    )
    actual_mw: float
    decision_error_mw: float
    first_error_mw: Optional[float]


class RevisionResponse(BaseModel):
    parameters: AnalysisParameters
    records: list[RevisionRecord]
    note: str = Field(
        default=(
            "Compares the decision forecast (latest vintage at or before cutoff) "
            "with the first available forecast for each delivery hour. "
            "revision_mw = decision_forecast − first_forecast."
        )
    )


# ------------------------------------------------------------------ #
# Business insights
# ------------------------------------------------------------------ #

class BusinessInsight(BaseModel):
    category: str
    severity: str = Field(description="'high', 'medium', 'low', or 'info'")
    title: str
    body: str
    supporting_data: dict = Field(default_factory=dict)


class InsightsResponse(BaseModel):
    parameters: AnalysisParameters
    n_insights: int
    insights: list[BusinessInsight]
    demand_disclaimer: str = Field(
        default=(
            "SCOPE LIMITATION: Consumer demand data is not available. "
            "These insights quantify wind generation forecast uncertainty only. "
            "They do not represent the quantity of electricity to procure, "
            "nor the residual demand to source from other market products."
        )
    )


# ------------------------------------------------------------------ #
# Day detail
# ------------------------------------------------------------------ #

class DayDetailResponse(BaseModel):
    date: str
    intervals: list[DayDetailInterval]
    daily_summary: Optional[SummaryMetrics] = None
    assumption_note: str = Field(
        default=(
            "ASSUMPTION A2: Accuracy metrics are computed only for on-the-hour (HH:00) intervals. "
            "WINDFOR forecasts are hourly; no half-hour forecast exists for HH:30 actuals."
        )
    )
