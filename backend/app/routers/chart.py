"""
GET /api/chart/day/{date} — per-day detail for the Day Detail page.

Returns 24 hourly intervals with:
  - forecast_mw (if available, day-ahead cutoff applied)
  - actual_mw_on_hour (HH:00 actual — used in metrics)
  - actual_mw_half_hour (HH:30 actual — display only)
  - error_mw, forecast_publish_time, lead_hours
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Path, Query

from app import cache as cache_module
from app.accuracy_service import compute_metrics
from app.config import get_settings
from app.models import DayDetailInterval, DayDetailResponse, SummaryMetrics

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get(
    "/chart/day/{date}",
    response_model=DayDetailResponse,
    summary="Per-day forecast vs actual detail (24 hourly intervals)",
    tags=["Chart"],
)
async def get_day_detail(
    date: date = Path(
        description="Settlement date (YYYY-MM-DD). Must be within 2026-01-01 to 2026-01-31.",
    ),
    cutoff_hour_utc: int = Query(
        default=9,
        ge=0,
        le=23,
        description="Day-ahead decision cutoff hour (UTC). Default 9 = 09:00 UTC (Assumption A1).",
    ),
) -> DayDetailResponse:
    """
    Returns the full 24-hour picture for a single delivery day.

    For each delivery hour (00:00 to 23:00):
    - **forecast_mw**: the day-ahead decision forecast (latest vintage published
      before `cutoff_hour_utc` on the previous day).
    - **actual_mw_on_hour**: the HH:00 actual from FUELHH — used in metrics.
    - **actual_mw_half_hour**: the HH:30 actual — displayed for context only
      (no matching forecast exists, Assumption A2).
    - **error_mw**: forecast − actual (positive = overforecast).

    Hours with no eligible day-ahead forecast are included with
    `forecast_mw = null` and `error_mw = null`.
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")

    # Validate date is within scope
    min_d = settings.analysis_date_min
    max_d = settings.analysis_date_max
    if not (min_d <= date <= max_d):
        raise HTTPException(
            404,
            detail=f"Date {date} is outside the analysis range ({min_d} to {max_d}).",
        )

    # ------------------------------------------------------------------ #
    # Pull actuals for this date (both HH:00 and HH:30)
    # ------------------------------------------------------------------ #
    actuals_df = state.actuals_df
    day_actuals = actuals_df[actuals_df["settlement_date"] == date].copy()

    on_hour  = day_actuals[day_actuals["is_on_hour"]].set_index("start_time")
    off_hour = day_actuals[~day_actuals["is_on_hour"]].set_index("start_time")

    # ------------------------------------------------------------------ #
    # Pull analysis (joined forecast + actual) for this date
    # ------------------------------------------------------------------ #
    joined_df = state.get_analysis(cutoff_hour=cutoff_hour_utc)
    day_joined = joined_df[joined_df["settlement_date"] == date].set_index("start_time")

    # ------------------------------------------------------------------ #
    # Build 24-interval response
    # ------------------------------------------------------------------ #
    intervals: list[DayDetailInterval] = []

    for hour in range(24):
        hour_ts   = pd.Timestamp(year=date.year, month=date.month, day=date.day,
                                  hour=hour, tz="UTC")
        half_ts   = hour_ts + pd.Timedelta(minutes=30)
        hour_str  = f"{hour:02d}:00"

        # On-hour actual (SP = odd: 1, 3, 5, … 47)
        sp_on_hour       = hour * 2 + 1
        actual_on_hour   = on_hour.loc[hour_ts, "generation_mw"] if hour_ts in on_hour.index else None
        actual_half_hour = off_hour.loc[half_ts, "generation_mw"] if half_ts in off_hour.index else None

        # Forecast and error (from joined analysis)
        if hour_ts in day_joined.index:
            row          = day_joined.loc[hour_ts]
            forecast_mw  = round(float(row["forecast_mw"]), 2)
            error_mw     = round(float(row["error_mw"]), 2)
            pub_time     = row["forecast_publish_time"]
            lead_hours   = round(float(row["lead_hours"]), 2)
        else:
            forecast_mw  = None
            error_mw     = None
            pub_time     = None
            lead_hours   = None

        intervals.append(DayDetailInterval(
            hour_utc=hour_str,
            start_time=hour_ts,
            settlement_period_on_hour=sp_on_hour,
            forecast_mw=forecast_mw,
            actual_mw_on_hour=round(float(actual_on_hour), 2) if actual_on_hour is not None else None,
            actual_mw_half_hour=round(float(actual_half_hour), 2) if actual_half_hour is not None else None,
            error_mw=error_mw,
            forecast_publish_time=pub_time,
            lead_hours=lead_hours,
        ))

    # ------------------------------------------------------------------ #
    # Daily summary metrics
    # ------------------------------------------------------------------ #
    daily_summary: SummaryMetrics | None = None
    if not day_joined.empty:
        from app.accuracy_service import compute_metrics as _cm
        m = _cm(day_joined.reset_index(), period_label=str(date), n_total_intervals=24)
        daily_summary = SummaryMetrics(
            period_label=m.period_label,
            n_matched_intervals=m.n_matched_intervals,
            n_total_intervals=m.n_total_intervals,
            coverage_pct=m.coverage_pct,
            mae_mw=m.mae_mw,
            rmse_mw=m.rmse_mw,
            mbe_mw=m.mbe_mw,
            mape_pct=m.mape_pct,
            nmae_pct=m.nmae_pct,
            mean_actual_mw=m.mean_actual_mw,
            mean_forecast_mw=m.mean_forecast_mw,
            mean_lead_hours=m.mean_lead_hours,
        )

    return DayDetailResponse(
        date=str(date),
        intervals=intervals,
        daily_summary=daily_summary,
    )
