"""GET /api/actuals — cached FUELHH wind actuals."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app import cache as cache_module
from app.config import get_settings
from app.models import ActualRecord, ActualsResponse

router = APIRouter()
settings = get_settings()


@router.get(
    "/actuals",
    response_model=ActualsResponse,
    summary="Half-hourly actual wind generation (FUELHH)",
    tags=["Data"],
)
async def get_actuals(
    start_date: date = Query(
        default=date(2026, 1, 1),
        description="First settlement date (YYYY-MM-DD). Min: 2026-01-01.",
    ),
    end_date: date = Query(
        default=date(2026, 1, 31),
        description="Last settlement date (YYYY-MM-DD). Max: 2026-01-31.",
    ),
    on_hour_only: bool = Query(
        default=False,
        description="If true, return only on-the-hour records (HH:00). "
                    "These are the records matched with forecasts.",
    ),
) -> ActualsResponse:
    """
    Returns cached actual wind generation from the Elexon FUELHH dataset.

    Each record represents one 30-minute settlement period.
    The **is_on_hour** flag identifies records at HH:00:00Z, which are the
    only ones that can be matched against WINDFOR hourly forecasts
    (Assumption A2 — resolution mismatch).

    **Data source**: Elexon BMRS FUELHH/stream, fuelType=WIND.
    """
    state = cache_module.get_cache()
    if not state.is_loaded:
        raise HTTPException(503, detail="Data not yet loaded. Check /api/health.")

    _validate_date_range(start_date, end_date)

    df = state.actuals_df.copy()

    # Filter to requested date range
    df = df[
        (df["settlement_date"] >= start_date) &
        (df["settlement_date"] <= end_date)
    ]

    if on_hour_only:
        df = df[df["is_on_hour"]]

    records = [
        ActualRecord(
            start_time=row.start_time,
            settlement_date=row.settlement_date,
            settlement_period=int(row.settlement_period),
            generation_mw=round(float(row.generation_mw), 2),
            publish_time=row.publish_time,
            is_on_hour=bool(row.is_on_hour),
        )
        for row in df.itertuples(index=False)
    ]

    return ActualsResponse(
        total_rows=len(records),
        on_hour_rows=sum(1 for r in records if r.is_on_hour),
        records=records,
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
