"""
In-memory data cache.

Stores the two cleaned DataFrames fetched at startup and memoises
the joined analysis DataFrame per cutoff_hour to avoid recomputing
vintage selection on every request.

Design rationale (architecture.md §4.4):
  January 2026 is historical — data will not change.
  Fetching once at startup and caching eliminates per-request Elexon
  latency and reduces load on the public API.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from app.accuracy_service import join_and_compute_errors
from app.vintage_service import select_decision_forecasts
from app.validation_service import ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class CacheState:
    """Encapsulates all cached data and metadata."""

    # Raw cleaned DataFrames (set once at startup)
    actuals_df: Optional[pd.DataFrame] = None
    forecasts_df: Optional[pd.DataFrame] = None

    # Validation reports (for /api/data/status)
    actuals_validation: Optional[ValidationReport] = None
    forecasts_validation: Optional[ValidationReport] = None

    # Memoised joined analysis DataFrames, keyed by cutoff_hour
    _analysis_cache: dict[int, pd.DataFrame] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Metadata
    loaded_at: Optional[datetime] = None
    load_error: Optional[str] = None

    # Row counts at load time
    negative_forecast_rows_clamped: int = 0

    @property
    def is_loaded(self) -> bool:
        return self.actuals_df is not None and self.forecasts_df is not None

    @property
    def actuals_rows(self) -> Optional[int]:
        return len(self.actuals_df) if self.actuals_df is not None else None

    @property
    def forecast_rows(self) -> Optional[int]:
        return len(self.forecasts_df) if self.forecasts_df is not None else None

    @property
    def unique_delivery_hours(self) -> Optional[int]:
        if self.forecasts_df is None:
            return None
        return int(self.forecasts_df["start_time"].nunique())

    @property
    def missing_actual_periods(self) -> Optional[int]:
        """Number of FUELHH settlement periods absent from the expected 1,488."""
        if self.actuals_df is None:
            return None
        expected = 31 * 48  # January 2026
        return max(0, expected - len(self.actuals_df))

    def get_analysis(self, cutoff_hour: int) -> pd.DataFrame:
        """
        Return (or compute and cache) the joined analysis DataFrame
        for the given cutoff_hour.

        Thread-safe via a lock — concurrent requests with the same
        cutoff_hour won't trigger duplicate computation.
        """
        with self._lock:
            if cutoff_hour not in self._analysis_cache:
                if not self.is_loaded:
                    raise RuntimeError("Cache not loaded — cannot compute analysis")
                logger.info(
                    "Cache miss for cutoff_hour=%d — computing vintage selection + join",
                    cutoff_hour,
                )
                decision_df = select_decision_forecasts(self.forecasts_df, cutoff_hour)
                joined_df   = join_and_compute_errors(self.actuals_df, decision_df)
                self._analysis_cache[cutoff_hour] = joined_df
                logger.info(
                    "Analysis cached for cutoff_hour=%d: %d matched pairs",
                    cutoff_hour, len(joined_df),
                )
            return self._analysis_cache[cutoff_hour]

    def invalidate(self) -> None:
        """Clear all cached data (used if a reload is triggered)."""
        with self._lock:
            self.actuals_df  = None
            self.forecasts_df = None
            self._analysis_cache.clear()
            self.loaded_at   = None
            self.load_error  = None
            logger.info("Cache invalidated")


# ------------------------------------------------------------------ #
# Module-level singleton
# ------------------------------------------------------------------ #

_state = CacheState()


def get_cache() -> CacheState:
    """Return the global cache state singleton."""
    return _state


def set_actuals(df: pd.DataFrame, report: ValidationReport) -> None:
    _state.actuals_df = df
    _state.actuals_validation = report
    logger.info("Cache: actuals_df set (%d rows)", len(df))


def set_forecasts(df: pd.DataFrame, report: ValidationReport) -> None:
    _state.forecasts_df = df
    _state.forecasts_validation = report
    logger.info("Cache: forecasts_df set (%d rows)", len(df))


def mark_loaded() -> None:
    _state.loaded_at = datetime.now(tz=timezone.utc)
    _state.load_error = None
    logger.info("Cache: marked as fully loaded at %s", _state.loaded_at.isoformat())


def mark_load_error(error: str) -> None:
    _state.load_error = error
    logger.error("Cache: load error — %s", error)
