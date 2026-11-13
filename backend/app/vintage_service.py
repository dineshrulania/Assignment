"""
Forecast vintage selection service.

This is the central analytical logic of the application.

Business problem (data_model.md §3):
  A procurement team must decide how much electricity to buy from the
  day-ahead market BEFORE seeing actual wind generation.  For each delivery
  hour H on delivery date D, the team would have used the most recent
  wind generation forecast available before the market deadline.

Vintage selection rule:
  For each delivery hour H:
    cutoff_dt = (D - 1 day) at <cutoff_hour>:00 UTC
    Decision forecast = the WINDFOR row where:
      • start_time == H
      • publish_time <= cutoff_dt
      • publish_time < start_time  (genuine forecast, not hindcast — already enforced upstream)
    … choosing the row with the MAXIMUM publish_time among candidates.

  If no candidate exists → delivery hour is excluded from accuracy metrics.

ASSUMPTION A1:
  Default cutoff_hour = 9 (09:00 UTC on D-1).
  The GB EPEX SPOT day-ahead auction closes ~09:20–09:50 UK local time
  on D-1.  January 2026 is GMT, so UK local == UTC.
  09:00 UTC gives traders a small margin before bid submission.
  This is an ANALYTICAL PROXY, not a confirmed trading rule.
  The cutoff_hour is a configurable parameter (0–23 UTC).
"""

from __future__ import annotations

import logging
from datetime import timezone

import pandas as pd

logger = logging.getLogger(__name__)
UTC = timezone.utc


def select_decision_forecasts(
    forecasts_df: pd.DataFrame,
    cutoff_hour: int = 9,
) -> pd.DataFrame:
    """
    Select the day-ahead decision forecast vintage for every delivery hour.

    Parameters
    ----------
    forecasts_df : pd.DataFrame
        Cleaned WINDFOR data from forecasts_service.build_forecasts_dataframe().
        Required columns: publish_time, start_time, generation_mw, lead_hours.
        All hindcasts must already have been dropped.

    cutoff_hour : int  (0–23 UTC, default 9)
        The latest publication hour (UTC) on D-1 to consider.
        ASSUMPTION A1: default 09:00 UTC.

    Returns
    -------
    pd.DataFrame
        One row per delivery hour that had an eligible forecast.
        Columns: start_time, forecast_mw, forecast_publish_time,
                 lead_hours, cutoff_hour.
    """
    if forecasts_df.empty:
        logger.warning("vintage_service: received empty forecasts DataFrame")
        return _empty_decision_df()

    if not (0 <= cutoff_hour <= 23):
        raise ValueError(f"cutoff_hour must be 0–23, got {cutoff_hour}")

    df = forecasts_df.copy()

    # ------------------------------------------------------------------ #
    # Compute cutoff_dt for each row
    # ------------------------------------------------------------------ #
    # For each delivery hour H on delivery date D:
    #   cutoff_dt = D-1 at cutoff_hour:00 UTC
    #
    # We compute D-1 by subtracting one day from start_time's date,
    # then constructing a full UTC datetime at cutoff_hour:00:00.
    #
    # Using .dt.normalize() to strip the time component, then subtract
    # one day and add the cutoff hour in nanoseconds.
    delivery_dates = df["start_time"].dt.normalize()  # midnight on delivery date
    cutoff_dt = (
        delivery_dates
        - pd.Timedelta(days=1)                          # D-1
        + pd.Timedelta(hours=cutoff_hour)               # at cutoff_hour:00 UTC
    )
    # cutoff_dt is timezone-aware (inherits from start_time which is UTC-aware)

    # ------------------------------------------------------------------ #
    # Filter to eligible vintages: publish_time <= cutoff_dt
    # ------------------------------------------------------------------ #
    eligible_mask = df["publish_time"] <= cutoff_dt
    eligible = df[eligible_mask].copy()

    n_total   = len(df)
    n_eligible = len(eligible)
    n_dropped  = n_total - n_eligible
    logger.info(
        "Vintage selection (cutoff_hour=%d UTC): %d/%d vintages eligible (dropped %d published after cutoff)",
        cutoff_hour, n_eligible, n_total, n_dropped,
    )

    if eligible.empty:
        logger.warning(
            "No eligible forecasts found with cutoff_hour=%d. "
            "Try a later cutoff hour.", cutoff_hour
        )
        return _empty_decision_df()

    # ------------------------------------------------------------------ #
    # For each delivery hour, select the latest publish_time  (max vintage)
    # ------------------------------------------------------------------ #
    # idxmax per group gives the row index with the highest publish_time.
    idx_max = eligible.groupby("start_time")["publish_time"].idxmax()
    decision = eligible.loc[idx_max].copy()

    # ------------------------------------------------------------------ #
    # Rename and annotate
    # ------------------------------------------------------------------ #
    decision = decision.rename(columns={
        "generation_mw": "forecast_mw",
        "publish_time":  "forecast_publish_time",
    })
    decision["cutoff_hour"] = cutoff_hour
    decision = decision[
        ["start_time", "forecast_mw", "forecast_publish_time", "lead_hours", "cutoff_hour"]
    ].sort_values("start_time").reset_index(drop=True)

    n_hours_covered = len(decision)
    n_hours_possible = forecasts_df["start_time"].nunique()
    logger.info(
        "Vintage selection complete: %d/%d delivery hours have a decision forecast "
        "(cutoff_hour=%d UTC, Assumption A1)",
        n_hours_covered, n_hours_possible, cutoff_hour,
    )

    return decision


def get_all_vintages_for_hour(
    forecasts_df: pd.DataFrame,
    delivery_hour: pd.Timestamp,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Return all forecast vintages for a specific delivery hour.

    Used by the /api/forecasts/versions endpoint to show how the
    forecast evolved as delivery approached.

    Parameters
    ----------
    forecasts_df : pd.DataFrame
        Cleaned WINDFOR data (all vintages, hindcasts already dropped).
    delivery_hour : pd.Timestamp
        The specific UTC delivery hour to look up.
    limit : int
        Maximum number of vintages to return (most recent first).

    Returns
    -------
    pd.DataFrame
        Columns: publish_time, start_time, generation_mw, lead_hours.
        Sorted by publish_time descending (most recent first).
    """
    mask = forecasts_df["start_time"] == delivery_hour
    result = (
        forecasts_df[mask]
        .sort_values("publish_time", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )
    return result


def _empty_decision_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "start_time", "forecast_mw", "forecast_publish_time",
        "lead_hours", "cutoff_hour",
    ])
