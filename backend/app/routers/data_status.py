"""GET /api/data/status — detailed data coverage and quality report."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import cache as cache_module
from app.config import get_settings
from app.models import DataStatusResponse

router = APIRouter()
settings = get_settings()


@router.get(
    "/data/status",
    response_model=DataStatusResponse,
    summary="Detailed data coverage and quality report",
    tags=["System"],
)
async def data_status() -> DataStatusResponse:
    """
    Returns detailed information about the cached data:

    - Row counts for actuals and forecasts.
    - Number of unique delivery hours covered by forecasts.
    - Number of missing actual settlement periods.
    - Number of negative forecast values that were clamped to zero.
    - The fetch window parameters used.
    """
    state = cache_module.get_cache()

    if not state.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Data not yet loaded. Check /api/health for status.",
        )

    return DataStatusResponse(
        cache_loaded=True,
        actuals_rows=state.actuals_rows,
        forecast_rows=state.forecast_rows,
        forecast_vintages=state.forecast_rows,
        unique_delivery_hours=state.unique_delivery_hours,
        actuals_date_from=settings.actuals_date_from,
        actuals_date_to=settings.actuals_date_to,
        forecasts_publish_from=settings.forecasts_publish_from,
        forecasts_publish_to=settings.forecasts_publish_to,
        missing_actual_periods=state.missing_actual_periods,
        negative_forecast_rows_clamped=state.negative_forecast_rows_clamped,
    )
