"""
Application configuration.

All tuneable values live here. Override any setting via environment variable.
Documented assumptions are labelled A1–A8 (see data_model.md §11).
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime settings loaded from environment variables (or .env file).

    Every field has a sensible default so the app starts without any
    configuration; production deployments override via env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Elexon API
    # ------------------------------------------------------------------ #
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 60.0
    elexon_max_retries: int = 3
    elexon_retry_backoff_base: float = 1.0  # seconds; doubles each attempt

    # ------------------------------------------------------------------ #
    # Data scope — January 2026 delivery window
    # ------------------------------------------------------------------ #
    # FUELHH actuals: settlement dates 2026-01-01 → 2026-01-31
    actuals_date_from: str = "2026-01-01"
    actuals_date_to: str = "2026-01-31"
    actuals_fuel_type: str = "WIND"

    # WINDFOR forecasts: publish window starts 2025-12-28 to capture the
    # day-ahead forecasts for 2026-01-01 delivery (published ~2025-12-31).
    # Window ends 2026-02-01 to capture all vintages for 2026-01-31 delivery.
    # See api_research.md §3.7 for derivation.
    forecasts_publish_from: str = "2025-12-28T00:00:00Z"
    forecasts_publish_to: str = "2026-02-01T00:00:00Z"

    # ------------------------------------------------------------------ #
    # Day-ahead decision cutoff — ASSUMPTION A1
    # ------------------------------------------------------------------ #
    # The GB EPEX SPOT day-ahead auction closes ~09:20–09:50 UK local time
    # on D-1.  January 2026 is GMT, so UK local == UTC.  We use 09:00 UTC
    # as the decision cutoff to give traders a margin before bid submission.
    # This is an analytical assumption, NOT a confirmed client trading rule.
    # The value is exposed as a configurable query parameter (0–23 UTC).
    default_cutoff_hour_utc: int = 9

    # ------------------------------------------------------------------ #
    # CORS / server
    # ------------------------------------------------------------------ #
    # Comma-separated list of allowed origins.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # ------------------------------------------------------------------ #
    # Analysis date range constraints
    # ------------------------------------------------------------------ #
    @property
    def analysis_date_min(self) -> date:
        return date(2026, 1, 1)

    @property
    def analysis_date_max(self) -> date:
        return date(2026, 1, 31)

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
