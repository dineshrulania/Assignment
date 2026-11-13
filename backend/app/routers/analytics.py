"""
Analytics endpoints.

GET /api/dashboard/summary    — composite dashboard response
GET /api/analytics/accuracy   — summary accuracy metrics
GET /api/analytics/daily      — per-day accuracy breakdown
GET /api/analytics/errors     — timeseries errors + distribution
GET /api/analytics/timeofday  — accuracy by hour of day
GET /api/analytics/revisions  — forecast revision analysis
GET /api/analytics/insights   — data-driven business insights

Business scope note:
  Consumer demand data is NOT available. All endpoints quantify wind generation
  forecast uncertainty only. They do not represent electricity procurement
  quantities or residual demand.

Timezone note (Assumption A5):
  January 2026 is entirely within GMT. UTC == GB local time.
  No DST adjustment is required for this period.
"""

from __future__ import annotations

import logging
import math
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app import cache as cache_module
from app.accuracy_service import (
    compute_daily_metrics,
    compute_error_distribution,
    compute_forecast_revision_analysis,
    compute_horizon_metrics,
    compute_metrics,
    compute_time_of_day_metrics,
    generate_business_insights,
)
from app.config import get_settings
from app.models import (
    AccuracyResponse,
    AnalysisParameters,
    BusinessInsight,
    DailyAnalyticsResponse,
    DailyMetrics,
    DashboardSummaryResponse,
    ErrorBin,
    ErrorDistributionResponse,
    ErrorsResponse,
    HorizonBucket,
    InsightsResponse,
    RevisionRecord,
    RevisionResponse,
    SummaryMetrics,
    TimeOfDayMetrics,
    TimeOfDayResponse,
    TimeseriesPoint,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

_ASSUMPTION_A1 = (
    "ASSUMPTION A1: Day-ahead cutoff defaults to 09:00 UTC on D-1. "
    "The GB EPEX SPOT auction closes ~09:20–09:50 UK local time "
    "(January 2026 is GMT, so UTC == GB local). "
    "This is an analytical proxy; the exact client trading deadline was not specified. "
    "SCOPE: These metrics quantify wind generation forecast uncertainty. "
    "They do not represent electricity procurement quantities."
)

_DEMAND_DISCLAIMER = (
    "Consumer demand data is not available in this application. "
    "Metrics quantify wind generation forecast uncertainty only and do not "
    "represent the quantity of electricity to procure."
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_filtered_joined(start_date: date, end_date: date, cutoff_hour_utc: int):
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")
    _validate_date_range(start_date, end_date)
    _validate_cutoff(cutoff_hour_utc)
    joined_df = state.get_analysis(cutoff_hour=cutoff_hour_utc)
    return joined_df[
        (joined_df["settlement_date"] >= start_date) &
        (joined_df["settlement_date"] <= end_date)
    ].copy()


def _validate_date_range(start_date: date, end_date: date) -> None:
    min_d, max_d = settings.analysis_date_min, settings.analysis_date_max
    if not (min_d <= start_date <= max_d):
        raise HTTPException(422, detail=f"start_date must be between {min_d} and {max_d}")
    if not (min_d <= end_date <= max_d):
        raise HTTPException(422, detail=f"end_date must be between {min_d} and {max_d}")
    if start_date > end_date:
        raise HTTPException(422, detail="start_date must not be after end_date")


def _validate_cutoff(h: int) -> None:
    if not (0 <= h <= 23):
        raise HTTPException(422, detail="cutoff_hour_utc must be 0–23")


def _n_total(start_date: date, end_date: date) -> int:
    return ((end_date - start_date).days + 1) * 24


def _to_summary(m) -> SummaryMetrics:
    return SummaryMetrics(
        period_label=m.period_label,
        n_matched_intervals=m.n_matched_intervals,
        n_total_intervals=m.n_total_intervals,
        coverage_pct=m.coverage_pct,
        mae_mw=m.mae_mw,
        rmse_mw=m.rmse_mw,
        mbe_mw=m.mbe_mw,
        mape_pct=m.mape_pct,
        mape_zero_exclusions=m.mape_zero_exclusions,
        nmae_pct=m.nmae_pct,
        mean_actual_mw=m.mean_actual_mw,
        mean_forecast_mw=m.mean_forecast_mw,
        mean_lead_hours=m.mean_lead_hours,
        over_forecast_count=m.over_forecast_count,
        under_forecast_count=m.under_forecast_count,
        over_forecast_pct=m.over_forecast_pct,
        under_forecast_pct=m.under_forecast_pct,
        max_over_forecast_mw=m.max_over_forecast_mw,
        max_under_forecast_mw=m.max_under_forecast_mw,
    )


def _to_timeseries(joined_df) -> list[TimeseriesPoint]:
    records = []
    for row in joined_df.itertuples(index=False):
        raw_pct = getattr(row, "pct_error", None)
        pct: float | None = None
        if raw_pct is not None:
            try:
                v = float(raw_pct)
                pct = None if math.isnan(v) else round(v, 2)
            except (TypeError, ValueError):
                pct = None
        records.append(TimeseriesPoint(
            start_time=row.start_time,
            settlement_date=row.settlement_date,
            settlement_period=int(row.settlement_period),
            forecast_mw=round(float(row.forecast_mw), 2),
            actual_mw=round(float(row.actual_mw), 2),
            forecast_publish_time=row.forecast_publish_time,
            lead_hours=round(float(row.lead_hours), 2),
            error_mw=round(float(row.error_mw), 2),
            abs_error_mw=round(float(row.abs_error_mw), 2),
            pct_error=pct,
        ))
    return records


def _to_daily(daily_list: list[dict]) -> list[DailyMetrics]:
    return [
        DailyMetrics(
            settlement_date=d["settlement_date"],
            n_intervals=d["n_intervals"],
            mean_forecast_mw=d["mean_forecast_mw"],
            mean_actual_mw=d["mean_actual_mw"],
            mae_mw=d["mae_mw"],
            mbe_mw=d["mbe_mw"],
            rmse_mw=d["rmse_mw"],
        )
        for d in daily_list
    ]


def _to_horizon(h_list: list[dict]) -> list[HorizonBucket]:
    return [
        HorizonBucket(
            bucket_label=h["bucket_label"],
            lead_hours_min=h["lead_hours_min"],
            lead_hours_max=h["lead_hours_max"],
            n_intervals=h["n_intervals"],
            mae_mw=h["mae_mw"],
            mbe_mw=h["mbe_mw"],
            rmse_mw=h["rmse_mw"],
        )
        for h in h_list
    ]


def _to_distribution(dist: dict, cutoff_hour: int) -> ErrorDistributionResponse:
    return ErrorDistributionResponse(
        cutoff_hour_utc=cutoff_hour,
        total_intervals=dist["total_intervals"],
        bins=[
            ErrorBin(
                bin_label=b["bin_label"],
                bin_min_mw=b["bin_min_mw"],
                bin_max_mw=b["bin_max_mw"],
                count=b["count"],
                pct_of_total=b["pct_of_total"],
            )
            for b in dist["bins"]
        ],
        mean_error_mw=dist["mean_error_mw"],
        std_error_mw=dist["std_error_mw"],
    )


def _params(start_date: date, end_date: date, cutoff: int) -> AnalysisParameters:
    return AnalysisParameters(
        start_date=str(start_date),
        end_date=str(end_date),
        cutoff_hour_utc=cutoff,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Composite dashboard: summary + timeseries + daily + horizon",
    tags=["Analytics"],
)
async def dashboard_summary(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(
        default=9, ge=0, le=23,
        description="Day-ahead decision cutoff hour UTC (Assumption A1). Default 9 = 09:00 UTC.",
    ),
) -> DashboardSummaryResponse:
    """
    Primary dashboard endpoint. All metrics quantify wind generation
    forecast uncertainty — not electricity procurement quantities.
    """
    df = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    p  = _params(start_date, end_date, cutoff_hour_utc)
    m  = compute_metrics(df, f"{start_date} to {end_date}", _n_total(start_date, end_date))

    return DashboardSummaryResponse(
        parameters=p,
        summary=_to_summary(m),
        timeseries=_to_timeseries(df),
        daily=_to_daily(compute_daily_metrics(df)),
        horizon=_to_horizon(compute_horizon_metrics(df)),
        assumption_note=_ASSUMPTION_A1,
    )


@router.get(
    "/analytics/accuracy",
    response_model=AccuracyResponse,
    summary="Forecast accuracy summary metrics (MAE, RMSE, MBE, MAPE, nMAE)",
    tags=["Analytics"],
)
async def get_accuracy(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> AccuracyResponse:
    """
    Accuracy metrics for the specified period and cutoff.

    Formulas:
    - MAE  = mean(|forecast − actual|)
    - RMSE = sqrt(mean((forecast − actual)²))
    - MBE  = mean(forecast − actual)   [positive = overforecast]
    - MAPE = mean(|error/actual|)×100  [computed over non-zero actuals only]
    - nMAE = MAE / mean(actual) × 100
    """
    df = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    m  = compute_metrics(df, f"{start_date} to {end_date}", _n_total(start_date, end_date))
    return AccuracyResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        summary=_to_summary(m),
        assumption_note=_ASSUMPTION_A1,
    )


@router.get(
    "/analytics/daily",
    response_model=DailyAnalyticsResponse,
    summary="Per-day accuracy breakdown",
    tags=["Analytics"],
)
async def get_daily(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> DailyAnalyticsResponse:
    df = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    return DailyAnalyticsResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        daily=_to_daily(compute_daily_metrics(df)),
    )


@router.get(
    "/analytics/errors",
    response_model=ErrorsResponse,
    summary="Hour-by-hour errors and error distribution histogram",
    tags=["Analytics"],
)
async def get_errors(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> ErrorsResponse:
    df   = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    dist = compute_error_distribution(df)
    return ErrorsResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        timeseries=_to_timeseries(df),
        distribution=_to_distribution(dist, cutoff_hour_utc),
    )


@router.get(
    "/analytics/timeofday",
    response_model=TimeOfDayResponse,
    summary="Forecast accuracy grouped by UTC hour of day",
    tags=["Analytics"],
)
async def get_time_of_day(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> TimeOfDayResponse:
    """
    Shows whether forecast performance varies by time of day.

    Useful for identifying whether certain delivery hours (e.g. overnight,
    morning ramp) are systematically harder to forecast than others.
    """
    df   = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    rows = compute_time_of_day_metrics(df)
    return TimeOfDayResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        hours=[
            TimeOfDayMetrics(
                hour_of_day=r["hour_of_day"],
                hour_label=r["hour_label"],
                n_intervals=r["n_intervals"],
                mean_forecast_mw=r["mean_forecast_mw"],
                mean_actual_mw=r["mean_actual_mw"],
                mae_mw=r["mae_mw"],
                mbe_mw=r["mbe_mw"],
                rmse_mw=r["rmse_mw"],
            )
            for r in rows
        ],
    )


@router.get(
    "/analytics/revisions",
    response_model=RevisionResponse,
    summary="Forecast revision analysis — first vs decision vintage",
    tags=["Analytics"],
)
async def get_revisions(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> RevisionResponse:
    """
    Compares the decision forecast (latest vintage at/before cutoff) with
    the first published forecast for each delivery hour.

    revision_mw = decision_forecast − first_forecast
    - Positive: forecast was revised upward
    - Negative: forecast was revised downward

    Helps procurement teams understand how much forecast revisions changed
    expected wind generation between initial publication and decision time.
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded.")

    df      = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    records = compute_forecast_revision_analysis(state.forecasts_df, df)

    return RevisionResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        records=[
            RevisionRecord(
                start_time=r["start_time"],
                first_forecast_mw=r["first_forecast_mw"],
                first_publish_time=r["first_publish_time"],
                decision_forecast_mw=r["decision_forecast_mw"],
                decision_publish_time=r["decision_publish_time"],
                revision_mw=r["revision_mw"],
                actual_mw=r["actual_mw"],
                decision_error_mw=r["decision_error_mw"],
                first_error_mw=r["first_error_mw"],
            )
            for r in records
        ],
    )


@router.get(
    "/analytics/insights",
    response_model=InsightsResponse,
    summary="Data-driven business insights for the procurement team",
    tags=["Analytics"],
)
async def get_insights(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
    cutoff_hour_utc: int = Query(default=9, ge=0, le=23),
) -> InsightsResponse:
    """
    Generates concise business insights derived from the calculated metrics.

    Every insight is backed by specific calculated values — no insight is
    generated unless the data supports it.

    Includes a mandatory scope-limitation note: consumer demand data is not
    available, so the insights describe wind generation uncertainty only.
    """
    df       = _get_filtered_joined(start_date, end_date, cutoff_hour_utc)
    n_total  = _n_total(start_date, end_date)
    label    = f"{start_date} to {end_date}"
    metrics  = compute_metrics(df, label, n_total)
    daily    = compute_daily_metrics(df)
    tod      = compute_time_of_day_metrics(df)
    raw      = generate_business_insights(df, metrics, daily, tod)

    return InsightsResponse(
        parameters=_params(start_date, end_date, cutoff_hour_utc),
        n_insights=len(raw),
        insights=[
            BusinessInsight(
                category=i["category"],
                severity=i["severity"],
                title=i["title"],
                body=i["body"],
                supporting_data=i["supporting_data"],
            )
            for i in raw
        ],
        demand_disclaimer=_DEMAND_DISCLAIMER,
    )
