"""
Actual generation service.

Cleans and normalises raw FUELHH API records into a typed Pandas DataFrame.

Cleaning steps (data_model.md §2.1):
  1. Filter fuelType == "WIND" (defensive; API-side filter already applied).
  2. Parse publishTime and startTime as timezone-aware UTC datetimes.
  3. Deduplicate: for each startTime, keep the row with the latest publishTime.
     Assumption A3 — handles Elexon republications of revised figures.
  4. Clamp negative generation to 0.  Assumption A6.
  5. Sort ascending by startTime.
  6. Add is_on_hour boolean.  Assumption A2 — only on-hour rows match forecasts.
  7. Validate coverage: expect 48 rows per settlement date; log missing periods.
"""

from __future__ import annotations

import logging
from datetime import timezone

import pandas as pd

from app.validation_service import ValidationReport, validate_fuelhh

logger = logging.getLogger(__name__)

UTC = timezone.utc


def build_actuals_dataframe(
    raw: list[dict],
) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Convert raw FUELHH API response into a clean, typed DataFrame.

    Parameters
    ----------
    raw : list[dict]
        Direct output of ElexonClient.fetch_fuelhh().

    Returns
    -------
    (df, report)
        df     : Cleaned DataFrame.  Columns:
                   start_time (datetime[UTC]), settlement_date (date),
                   settlement_period (int64), generation_mw (float64),
                   publish_time (datetime[UTC]), is_on_hour (bool)
        report : ValidationReport with counts.
    """
    if not raw:
        logger.error("FUELHH: received empty response from Elexon")
        _, report = validate_fuelhh([])
        return _empty_actuals_df(), report

    # Validate before processing
    clean_raw, report = validate_fuelhh(raw)

    if not clean_raw:
        logger.error("FUELHH: no rows survived validation")
        return _empty_actuals_df(), report

    df = pd.DataFrame(clean_raw)

    # ------------------------------------------------------------------ #
    # Step 1 — rename columns to snake_case
    # ------------------------------------------------------------------ #
    df = df.rename(columns={
        "publishTime":      "publish_time",
        "startTime":        "start_time",
        "settlementDate":   "settlement_date",
        "settlementPeriod": "settlement_period",
        "fuelType":         "fuel_type",
        "generation":       "generation_mw",
    })

    # ------------------------------------------------------------------ #
    # Step 2 — type coercion
    # ------------------------------------------------------------------ #
    # Parse datetimes as UTC-aware.  utc=True makes pandas keep tz info.
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True)
    df["settlement_date"] = pd.to_datetime(df["settlement_date"]).dt.date
    df["settlement_period"] = df["settlement_period"].astype("int64")
    df["generation_mw"] = pd.to_numeric(df["generation_mw"], errors="coerce")

    # ------------------------------------------------------------------ #
    # Step 3 — defensive fuel-type filter (Assumption A7)
    # ------------------------------------------------------------------ #
    before = len(df)
    df = df[df["fuel_type"].str.upper() == "WIND"].copy()
    if len(df) < before:
        logger.warning("FUELHH: dropped %d non-WIND rows", before - len(df))

    # ------------------------------------------------------------------ #
    # Step 4 — clamp negative generation to 0  (Assumption A6)
    # ------------------------------------------------------------------ #
    neg_mask = df["generation_mw"] < 0
    n_neg = neg_mask.sum()
    if n_neg > 0:
        logger.warning(
            "FUELHH: clamping %d negative generation_mw values to 0  (Assumption A6)", n_neg
        )
        df.loc[neg_mask, "generation_mw"] = 0.0

    # ------------------------------------------------------------------ #
    # Step 5 — deduplicate: keep latest publish_time per start_time  (A3)
    # ------------------------------------------------------------------ #
    before_dedup = len(df)
    df = (
        df.sort_values("publish_time", ascending=True)
          .drop_duplicates(subset=["start_time"], keep="last")
    )
    n_dupes = before_dedup - len(df)
    if n_dupes > 0:
        logger.info(
            "FUELHH: deduplicated %d rows (kept latest publish_time per start_time, Assumption A3)",
            n_dupes,
        )

    # ------------------------------------------------------------------ #
    # Step 6 — sort by start_time ascending
    # ------------------------------------------------------------------ #
    df = df.sort_values("start_time").reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Step 7 — add is_on_hour flag  (Assumption A2)
    # ------------------------------------------------------------------ #
    df["is_on_hour"] = df["start_time"].dt.minute == 0

    # ------------------------------------------------------------------ #
    # Step 8 — keep only the columns we need
    # ------------------------------------------------------------------ #
    df = df[["start_time", "settlement_date", "settlement_period",
             "generation_mw", "publish_time", "is_on_hour"]].copy()

    # ------------------------------------------------------------------ #
    # Step 9 — coverage check: expect 48 rows per settlement date
    # ------------------------------------------------------------------ #
    _check_coverage(df)

    logger.info(
        "Actuals DataFrame built: %d rows total, %d on-hour rows",
        len(df),
        df["is_on_hour"].sum(),
    )
    return df, report


def _check_coverage(df: pd.DataFrame) -> None:
    """Log any settlement dates with fewer than 48 periods."""
    counts = df.groupby("settlement_date").size()
    missing_dates = counts[counts < 48]
    if not missing_dates.empty:
        for dt, count in missing_dates.items():
            logger.warning(
                "FUELHH: settlement_date %s has only %d/48 periods",
                dt, count,
            )
    else:
        logger.info("FUELHH: all settlement dates have full 48-period coverage")


def _empty_actuals_df() -> pd.DataFrame:
    """Return an empty DataFrame with the correct schema."""
    return pd.DataFrame(columns=[
        "start_time", "settlement_date", "settlement_period",
        "generation_mw", "publish_time", "is_on_hour",
    ])
