"""
Forecast generation service.

Cleans and normalises raw WINDFOR API records into a typed Pandas DataFrame.

Cleaning steps (data_model.md §2.2):
  1. Parse publishTime and startTime as timezone-aware UTC datetimes.
  2. Clamp negative generation to 0.  Assumption A6.
  3. Drop hindcasts: retain only rows where startTime > publishTime.  Assumption A4.
     Hindcasts are rows describing the past, not genuine forecasts.
  4. Compute lead_hours = (startTime − publishTime) in hours.
  5. Sort by (start_time, publish_time) ascending.

Important (api_research.md §3.5):
  WINDFOR is HOURLY — forecasts only exist at HH:00:00Z.
  FUELHH is HALF-HOURLY — actuals exist at HH:00:00Z AND HH:30:00Z.
  This mismatch means accuracy metrics are computed on 744 matched points,
  not 1,488.  See Assumption A2.
"""

from __future__ import annotations

import logging
from datetime import date, timezone

import pandas as pd

from app.validation_service import ValidationReport, validate_windfor

logger = logging.getLogger(__name__)

UTC = timezone.utc

# January 2026 delivery date boundaries
_JAN_2026_START = pd.Timestamp("2026-01-01T00:00:00Z")
_FEB_2026_START = pd.Timestamp("2026-02-01T00:00:00Z")


def build_forecasts_dataframe(
    raw: list[dict],
) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Convert raw WINDFOR API response into a clean, typed DataFrame.

    Parameters
    ----------
    raw : list[dict]
        Direct output of ElexonClient.fetch_windfor().

    Returns
    -------
    (df, report)
        df     : Cleaned DataFrame.  Columns:
                   publish_time (datetime[UTC]),
                   start_time (datetime[UTC]),
                   generation_mw (float64),
                   lead_hours (float64)
        report : ValidationReport with counts.

    Note: df contains ALL vintages for January 2026 delivery hours.
    Vintage selection (choosing the day-ahead decision forecast) is done
    separately in vintage_service.py.
    """
    if not raw:
        logger.error("WINDFOR: received empty response from Elexon")
        _, report = validate_windfor([])
        return _empty_forecasts_df(), report

    # Validate
    clean_raw, report = validate_windfor(raw)

    if not clean_raw:
        logger.error("WINDFOR: no rows survived validation")
        return _empty_forecasts_df(), report

    df = pd.DataFrame(clean_raw)

    # ------------------------------------------------------------------ #
    # Step 1 — rename to snake_case
    # ------------------------------------------------------------------ #
    df = df.rename(columns={
        "publishTime": "publish_time",
        "startTime":   "start_time",
        "generation":  "generation_mw",
    })

    # ------------------------------------------------------------------ #
    # Step 2 — parse datetimes as UTC-aware
    # ------------------------------------------------------------------ #
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True)
    df["start_time"]   = pd.to_datetime(df["start_time"],   utc=True)
    df["generation_mw"] = pd.to_numeric(df["generation_mw"], errors="coerce")

    # Drop rows where datetime parsing failed
    n_before = len(df)
    df = df.dropna(subset=["publish_time", "start_time", "generation_mw"])
    if len(df) < n_before:
        logger.warning("WINDFOR: dropped %d rows with unparseable datetimes/generation",
                       n_before - len(df))

    # ------------------------------------------------------------------ #
    # Step 3 — clamp negative generation to 0  (Assumption A6)
    # ------------------------------------------------------------------ #
    neg_mask = df["generation_mw"] < 0
    n_neg = neg_mask.sum()
    if n_neg > 0:
        logger.warning(
            "WINDFOR: clamping %d negative generation_mw values to 0  (Assumption A6)", n_neg
        )
        df.loc[neg_mask, "generation_mw"] = 0.0
    report.rows_negative_generation = int(n_neg)

    # ------------------------------------------------------------------ #
    # Step 4 — drop hindcasts: keep only start_time > publish_time  (A4)
    # ------------------------------------------------------------------ #
    n_before_hindcast = len(df)
    df = df[df["start_time"] > df["publish_time"]].copy()
    n_hindcasts = n_before_hindcast - len(df)
    if n_hindcasts > 0:
        logger.info(
            "WINDFOR: dropped %d hindcasts (start_time <= publish_time, Assumption A4)",
            n_hindcasts,
        )

    # ------------------------------------------------------------------ #
    # Step 5 — filter to January 2026 delivery window
    # ------------------------------------------------------------------ #
    # We fetched from 2025-12-28 to capture day-ahead forecasts for Jan 1.
    # Now restrict startTime to January 2026 so only relevant forecasts remain.
    n_before_filter = len(df)
    df = df[
        (df["start_time"] >= _JAN_2026_START) &
        (df["start_time"] <  _FEB_2026_START)
    ].copy()
    n_filtered = n_before_filter - len(df)
    logger.info(
        "WINDFOR: filtered to January 2026 delivery window — removed %d rows outside window, %d remain",
        n_filtered, len(df),
    )

    # ------------------------------------------------------------------ #
    # Step 6 — compute lead_hours
    # ------------------------------------------------------------------ #
    df["lead_hours"] = (
        (df["start_time"] - df["publish_time"])
        .dt.total_seconds() / 3600.0
    )

    # ------------------------------------------------------------------ #
    # Step 7 — sort by (start_time, publish_time)
    # ------------------------------------------------------------------ #
    df = df.sort_values(["start_time", "publish_time"]).reset_index(drop=True)

    # Keep only the columns we need
    df = df[["publish_time", "start_time", "generation_mw", "lead_hours"]].copy()

    n_unique_hours = df["start_time"].nunique()
    logger.info(
        "Forecasts DataFrame built: %d vintages across %d unique delivery hours",
        len(df), n_unique_hours,
    )
    return df, report


def _empty_forecasts_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["publish_time", "start_time",
                                  "generation_mw", "lead_hours"])
