"""GET /api/health — backend and cache status."""

from __future__ import annotations

from fastapi import APIRouter

from app import cache as cache_module
from app.models import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Backend health and cache status",
    tags=["System"],
)
async def health() -> HealthResponse:
    """
    Returns the operational status of the backend service.

    - **status**: 'ok' when both datasets are loaded; 'degraded' otherwise.
    - **cache_loaded**: true when FUELHH and WINDFOR data are in memory.
    - **actuals_rows**: number of FUELHH rows cached (expected 1,488 for Jan 2026).
    - **forecast_rows**: number of WINDFOR rows after hindcast removal.
    - **data_period**: settlement date range of the actuals.
    - **error**: present only when the last load attempt failed.
    """
    state = cache_module.get_cache()

    if state.is_loaded:
        return HealthResponse(
            status="ok",
            cache_loaded=True,
            actuals_rows=state.actuals_rows,
            forecast_rows=state.forecast_rows,
            data_period="2026-01-01 to 2026-01-31",
            error=None,
        )
    else:
        return HealthResponse(
            status="degraded",
            cache_loaded=False,
            actuals_rows=None,
            forecast_rows=None,
            data_period=None,
            error=state.load_error or "Data not yet loaded",
        )
