"""
FastAPI application entry point.

Startup sequence:
  1. Configure logging.
  2. Register CORS middleware.
  3. On lifespan start: fetch both Elexon datasets, clean, and populate cache.
  4. Register all routers.

Failure during startup is non-fatal: the app starts, /api/health reports
"degraded", and all data endpoints return 503 until a reload is triggered.
This design avoids a situation where a transient Elexon outage prevents
the backend from starting at all.
"""

from __future__ import annotations

import logging
import logging.config
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import cache as cache_module
from app.actuals_service import build_actuals_dataframe
from app.config import get_settings
from app.elexon_client import ElexonAPIError, fetch_all_data
from app.forecasts_service import build_forecasts_dataframe
from app.routers import (
    actuals,
    analytics,
    chart,
    data_status,
    forecasts,
    health,
)
# New analytics sub-endpoints are part of the analytics router — no separate import needed.

# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ------------------------------------------------------------------ #
# Lifespan (replaces deprecated @app.on_event("startup"))
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Fetch and cache Elexon data at startup.

    If the Elexon API is unreachable, the app continues in a degraded
    state so health checks and documentation remain accessible.
    """
    logger.info("=" * 60)
    logger.info("Wind Generation Forecast Analytics — backend starting")
    logger.info("=" * 60)

    t0 = time.monotonic()
    try:
        fuelhh_raw, windfor_raw = await fetch_all_data()

        actuals_df, actuals_report   = build_actuals_dataframe(fuelhh_raw)
        forecasts_df, forecast_report = build_forecasts_dataframe(windfor_raw)

        cache_module.set_actuals(actuals_df, actuals_report)
        cache_module.set_forecasts(forecasts_df, forecast_report)

        # Track negative forecast rows for /api/data/status
        state = cache_module.get_cache()
        state.negative_forecast_rows_clamped = forecast_report.rows_negative_generation

        cache_module.mark_loaded()

        elapsed = time.monotonic() - t0
        logger.info(
            "Startup complete in %.1fs: %d actuals rows, %d forecast vintages",
            elapsed,
            len(actuals_df),
            len(forecasts_df),
        )

        # Pre-warm the default cutoff (saves time on first dashboard request)
        logger.info("Pre-warming analysis cache for default cutoff_hour=%d…",
                    settings.default_cutoff_hour_utc)
        _ = state.get_analysis(settings.default_cutoff_hour_utc)
        logger.info("Analysis cache pre-warmed.")

    except ElexonAPIError as exc:
        elapsed = time.monotonic() - t0
        msg = f"Failed to fetch Elexon data at startup ({elapsed:.1f}s): {exc}"
        logger.error(msg)
        cache_module.mark_load_error(str(exc))

    except Exception as exc:
        elapsed = time.monotonic() - t0
        msg = f"Unexpected error during startup ({elapsed:.1f}s): {exc}"
        logger.exception(msg)
        cache_module.mark_load_error(str(exc))

    yield  # Application runs

    logger.info("Backend shutting down.")


# ------------------------------------------------------------------ #
# FastAPI application
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Wind Generation Forecast Analytics API",
    description=(
        "Evaluates National Grid ESO wind generation forecasts (WINDFOR) "
        "against actual half-hourly generation (FUELHH) from Elexon BMRS "
        "for January 2026 delivery. Supports day-ahead procurement decisions.\n\n"
        "**Data sources**: Elexon BMRS Insights API (no authentication required).\n"
        "**Assumption A1**: Day-ahead cutoff defaults to 09:00 UTC on D-1 "
        "(configurable). The GB EPEX SPOT auction closes ~09:20–09:50 UK local "
        "time (GMT in January = UTC). This is an analytical proxy.\n"
        "**Assumption A2**: Accuracy metrics are computed only for on-the-hour "
        "(HH:00) delivery intervals — WINDFOR is hourly, FUELHH is half-hourly."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ------------------------------------------------------------------ #
# CORS
# ------------------------------------------------------------------ #

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


# ------------------------------------------------------------------ #
# Global exception handlers
# ------------------------------------------------------------------ #

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred. See server logs."},
    )


# ------------------------------------------------------------------ #
# Router registration — all prefixed with /api
# ------------------------------------------------------------------ #

app.include_router(health.router,      prefix="/api", tags=["System"])
app.include_router(data_status.router, prefix="/api", tags=["System"])
app.include_router(actuals.router,     prefix="/api", tags=["Data"])
app.include_router(forecasts.router,   prefix="/api", tags=["Data"])
app.include_router(analytics.router,   prefix="/api", tags=["Analytics"])
app.include_router(chart.router,       prefix="/api", tags=["Chart"])


# ------------------------------------------------------------------ #
# Root redirect to docs
# ------------------------------------------------------------------ #

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
