"""
Forecast endpoints:
  GET /api/forecasts          — all cleaned WINDFOR vintages
  GET /api/forecasts/latest   — latest available vintage per delivery hour (no cutoff)
  GET /api/forecasts/versions — all vintages for a specific delivery hour
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

import pandas as pd

from app import cache as cache_module
from app.config import get_settings
from app.models import (
    ForecastRecord,
    ForecastsResponse,
    ForecastVintagesResponse,
    LatestForecastRecord,
    LatestForecastsResponse,
)
from app.vintage_service import get_all_vintages_for_hour

router = APIRouter()
settings = get_settings()
UTC = timezone.utc


@router.get(
    "/forecasts",
    response_model=ForecastsResponse,
    summary="All cleaned WINDFOR forecast vintages for January 2026 delivery",
    tags=["Data"],
)
async def get_forecasts(
    start_date: date = Query(
        default=date(2026, 1, 1),
        description="Filter by delivery date from (YYYY-MM-DD)",
    ),
    end_date: date = Query(
        default=date(2026, 1, 31),
        description="Filter by delivery date to (YYYY-MM-DD)",
    ),
    limit: int = Query(
        default=500,
        ge=1,
        le=20000,
        description="Maximum number of records to return",
    ),
) -> ForecastsResponse:
    """
    Returns all cleaned forecast vintages.

    Each record is a (`publishTime`, `startTime`) pair from WINDFOR,
    representing a single forecast for a single delivery hour.

    **Note**: This endpoint returns ALL vintages.  For procurement analysis,
    use the day-ahead decision forecast via `/api/analytics/accuracy`.

    Hindcasts (rows where `startTime <= publishTime`) have already been
    removed (Assumption A4).
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")

    _validate_date_range(start_date, end_date)

    df = state.forecasts_df.copy()

    # Filter to delivery date range
    df = df[
        (df["start_time"].dt.date >= start_date) &
        (df["start_time"].dt.date <= end_date)
    ]

    total_vintages    = len(df)
    unique_hours      = int(df["start_time"].nunique())

    # Apply limit (most recent vintages first)
    df = df.sort_values("publish_time", ascending=False).head(limit)

    records = [
        ForecastRecord(
            publish_time=row.publish_time,
            start_time=row.start_time,
            generation_mw=round(float(row.generation_mw), 2),
            lead_hours=round(float(row.lead_hours), 2),
        )
        for row in df.itertuples(index=False)
    ]

    return ForecastsResponse(
        total_vintages=total_vintages,
        unique_delivery_hours=unique_hours,
        records=records,
    )


@router.get(
    "/forecasts/latest",
    response_model=LatestForecastsResponse,
    summary="Latest available forecast vintage per delivery hour (no day-ahead cutoff applied)",
    tags=["Data"],
)
async def get_latest_forecasts(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date   = Query(default=date(2026, 1, 31)),
) -> LatestForecastsResponse:
    """
    Returns the most recently published forecast for each January 2026
    delivery hour, **without** applying a day-ahead cutoff.

    **Important**: These are the most accurate forecasts in hindsight
    (minimum lead time), not the forecasts that were available to the
    procurement team at their decision time.

    For day-ahead procurement analysis, use `/api/analytics/accuracy`.
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")

    _validate_date_range(start_date, end_date)

    df = state.forecasts_df.copy()
    df = df[
        (df["start_time"].dt.date >= start_date) &
        (df["start_time"].dt.date <= end_date)
    ]

    # Latest vintage per delivery hour = row with max publish_time per start_time
    idx_max = df.groupby("start_time")["publish_time"].idxmax()
    latest  = df.loc[idx_max].sort_values("start_time").reset_index(drop=True)

    records = [
        LatestForecastRecord(
            start_time=row.start_time,
            generation_mw=round(float(row.generation_mw), 2),
            publish_time=row.publish_time,
            lead_hours=round(float(row.lead_hours), 2),
        )
        for row in latest.itertuples(index=False)
    ]

    return LatestForecastsResponse(
        cutoff_note=(
            "These are the latest available vintages per delivery hour. "
            "They are NOT the day-ahead decision forecasts used in procurement analysis. "
            "Use /api/analytics/accuracy for day-ahead forecast evaluation."
        ),
        records=records,
    )


@router.get(
    "/forecasts/versions",
    response_model=ForecastVintagesResponse,
    summary="All forecast vintages for a single delivery hour",
    tags=["Data"],
)
async def get_forecast_versions(
    delivery_hour: str = Query(
        description="ISO-8601 UTC delivery hour, e.g. '2026-01-15T14:00:00Z'",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> ForecastVintagesResponse:
    """
    Returns all forecast vintages published for a specific delivery hour.

    Shows how the wind generation forecast evolved over time as delivery
    approached — useful for understanding forecast revision patterns.

    The vintages are ordered by publish time (most recent first).
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")

    # Parse and validate the delivery_hour parameter
    try:
        ts = pd.Timestamp(delivery_hour, tz="UTC")
    except Exception:
        raise HTTPException(
            422,
            detail=f"Invalid delivery_hour format: '{delivery_hour}'. "
                   "Expected ISO-8601 UTC, e.g. '2026-01-15T14:00:00Z'.",
        )

    if ts.minute != 0 or ts.second != 0:
        raise HTTPException(
            422,
            detail="delivery_hour must be on the hour (HH:00:00Z). "
                   "WINDFOR forecasts only exist at whole hours.",
        )

    min_dt = pd.Timestamp("2026-01-01T00:00:00Z")
    max_dt = pd.Timestamp("2026-01-31T23:00:00Z")
    if not (min_dt <= ts <= max_dt):
        raise HTTPException(
            404,
            detail=f"delivery_hour {delivery_hour} is outside January 2026. "
                   "This application covers 2026-01-01 to 2026-01-31.",
        )

    vintages_df = get_all_vintages_for_hour(state.forecasts_df, ts, limit=limit)

    if vintages_df.empty:
        raise HTTPException(
            404,
            detail=f"No forecast vintages found for delivery_hour {delivery_hour}.",
        )

    records = [
        ForecastRecord(
            publish_time=row.publish_time,
            start_time=row.start_time,
            generation_mw=round(float(row.generation_mw), 2),
            lead_hours=round(float(row.lead_hours), 2),
        )
        for row in vintages_df.itertuples(index=False)
    ]

    return ForecastVintagesResponse(
        delivery_hour=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        n_vintages=len(records),
        vintages=records,
    )


def _validate_date_range(start_date: date, end_date: date) -> None:
    min_d = settings.analysis_date_min
    max_d = settings.analysis_date_max
    if start_date < min_d or start_date > max_d:
        raise HTTPException(422, detail=f"start_date must be between {min_d} and {max_d}")
    if end_date < min_d or end_date > max_d:
        raise HTTPException(422, detail=f"end_date must be between {min_d} and {max_d}")
    if start_date > end_date:
        raise HTTPException(422, detail="start_date must not be after end_date")
