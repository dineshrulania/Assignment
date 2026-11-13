"""
Forecast accuracy calculation service.

AUDIT STATUS: Reviewed and verified 2026-01-xx against data_model.md §4–7.

Formula verification
--------------------
MAE  = mean(|forecast_i - actual_i|)                        ✓ uses abs_error_mw column
RMSE = sqrt(mean((forecast_i - actual_i)²))                 ✓ uses sq_error_mw2 column
MBE  = mean(forecast_i - actual_i)         (signed bias)    ✓ uses error_mw column
MAPE = mean(|forecast_i - actual_i| / |actual_i|) * 100     ✓ FIXED: computed over
       non-zero actuals only; exclusion count is reported.
nMAE = MAE / mean(actual_mw) * 100                          ✓

Error sign convention:
  error_mw = forecast_mw − actual_mw
  Positive → overforecast (forecast > actual) → wind was lower than predicted
             → buyer who relied on forecast may have under-purchased electricity
  Negative → underforecast (forecast < actual) → wind was higher than predicted
             → buyer may have over-purchased electricity

Business scope reminder:
  Consumer demand data is NOT available. These metrics quantify wind generation
  forecast uncertainty only. The dashboard supports procurement decisions by
  showing how much wind generation deviated from day-ahead expectations.
  It does NOT calculate the actual quantity of electricity to procure.

Timezone note (Assumption A5):
  January 2026 is entirely within GMT (UK does not observe DST in January).
  UTC == GB local time throughout. No DST transitions affect this dataset.
  All timestamps in this module are UTC-aware pandas Timestamps.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Horizon buckets (lead-time analysis)
# ---------------------------------------------------------------------------
# Day-ahead procurement window is typically 24–36h ahead.
# Buckets below and above provide context on accuracy vs lead time.
HORIZON_BUCKETS: list[tuple[str, float, float]] = [
    ("0–12h",  0,   12),
    ("12–18h", 12,  18),
    ("18–24h", 18,  24),
    ("24–30h", 24,  30),   # ← primary day-ahead window
    ("30–36h", 30,  36),   # ← primary day-ahead window
    ("36–48h", 36,  48),
    ("48h+",   48,  9999),
]


@dataclass
class AccuracyMetrics:
    """
    All accuracy metrics for a given period.

    Attributes
    ----------
    period_label          : Human-readable period description.
    n_matched_intervals   : Delivery hours with BOTH a decision forecast AND an actual.
    n_total_intervals     : Expected delivery hours in the period (24 × days).
    coverage_pct          : n_matched / n_total × 100.
    mae_mw                : Mean Absolute Error (MW).
    rmse_mw               : Root Mean Square Error (MW). Penalises outliers more than MAE.
    mbe_mw                : Mean Bias Error (MW). Positive = systematic overforecast.
    mape_pct              : Mean Absolute Percentage Error (%). None if all actuals are zero.
    mape_zero_exclusions  : Number of intervals excluded from MAPE due to zero actual.
    nmae_pct              : Normalised MAE = MAE / mean(actual) × 100.
    mean_actual_mw        : Mean actual wind generation over matched intervals.
    mean_forecast_mw      : Mean forecast wind generation over matched intervals.
    mean_lead_hours       : Mean forecast lead time over matched intervals.
    over_forecast_count   : Intervals where forecast > actual (error_mw > 0).
    under_forecast_count  : Intervals where forecast < actual (error_mw < 0).
    over_forecast_pct     : over_forecast_count / n_matched × 100.
    under_forecast_pct    : under_forecast_count / n_matched × 100.
    max_over_forecast_mw  : Largest single overforecast error (MW).
    max_under_forecast_mw : Largest single underforecast error magnitude (MW).
    """
    period_label: str
    n_matched_intervals: int
    n_total_intervals: int
    coverage_pct: float
    mae_mw: float
    rmse_mw: float
    mbe_mw: float
    mape_pct: Optional[float]
    mape_zero_exclusions: int
    nmae_pct: float
    mean_actual_mw: float
    mean_forecast_mw: float
    mean_lead_hours: float
    over_forecast_count: int
    under_forecast_count: int
    over_forecast_pct: float
    under_forecast_pct: float
    max_over_forecast_mw: float
    max_under_forecast_mw: float


def join_and_compute_errors(
    actuals_df: pd.DataFrame,
    decision_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Inner-join decision forecasts with on-the-hour actuals and compute error columns.

    ASSUMPTION A2: Only on-the-hour (HH:00:00Z) actuals participate in accuracy
    calculations. WINDFOR forecasts are hourly; there is no corresponding forecast
    for HH:30 settlement periods. Half-hour actuals remain in actuals_df for
    display purposes but are excluded from this join.

    Match key: start_time (UTC datetime, exact equality).
    Both sides must have UTC-aware datetimes — this is enforced during ingestion.

    Parameters
    ----------
    actuals_df : pd.DataFrame
        From actuals_service.build_actuals_dataframe().
        Must have columns: start_time, settlement_date, settlement_period,
        generation_mw, publish_time, is_on_hour.
    decision_df : pd.DataFrame
        From vintage_service.select_decision_forecasts().
        Must have columns: start_time, forecast_mw, forecast_publish_time,
        lead_hours, cutoff_hour.

    Returns
    -------
    pd.DataFrame with columns:
        start_time, settlement_date, settlement_period,
        forecast_mw, actual_mw, actual_publish_time,
        forecast_publish_time, lead_hours, cutoff_hour,
        error_mw, abs_error_mw, sq_error_mw2, pct_error
    """
    if actuals_df.empty or decision_df.empty:
        logger.warning(
            "join_and_compute_errors: one or both inputs are empty "
            "(actuals=%d rows, decisions=%d rows) — returning empty DataFrame",
            len(actuals_df), len(decision_df),
        )
        return _empty_joined_df()

    # Only on-the-hour actuals (Assumption A2)
    on_hour_actuals = actuals_df[actuals_df["is_on_hour"]].copy()
    on_hour_actuals = on_hour_actuals.rename(
        columns={
            "generation_mw": "actual_mw",
            "publish_time":  "actual_publish_time",
        }
    )

    # Verify both sides are UTC-aware before joining (defensive)
    _assert_utc_aware(decision_df["start_time"],    "decision_df.start_time")
    _assert_utc_aware(on_hour_actuals["start_time"], "on_hour_actuals.start_time")

    joined = decision_df.merge(
        on_hour_actuals[[
            "start_time", "settlement_date", "settlement_period",
            "actual_mw", "actual_publish_time",
        ]],
        on="start_time",
        how="inner",
    )

    logger.info(
        "join_and_compute_errors: %d decision forecasts × %d on-hour actuals → %d matched pairs",
        len(decision_df), len(on_hour_actuals), len(joined),
    )

    if joined.empty:
        logger.warning(
            "join_and_compute_errors: inner join produced zero rows. "
            "Check that start_time values are UTC-aware on both sides and "
            "that the delivery date ranges overlap."
        )
        return _empty_joined_df()

    # ── Error columns ────────────────────────────────────────────────────
    # error = forecast − actual  (sign: positive = overforecast)
    joined["error_mw"]     = joined["forecast_mw"] - joined["actual_mw"]
    joined["abs_error_mw"] = joined["error_mw"].abs()
    joined["sq_error_mw2"] = joined["error_mw"] ** 2

    # Percentage error: NaN when actual == 0 (division undefined)
    with np.errstate(divide="ignore", invalid="ignore"):
        joined["pct_error"] = np.where(
            joined["actual_mw"] != 0,
            (joined["error_mw"] / joined["actual_mw"]) * 100.0,
            np.nan,
        )

    return joined.sort_values("start_time").reset_index(drop=True)


def compute_metrics(
    joined_df: pd.DataFrame,
    period_label: str,
    n_total_intervals: int,
) -> AccuracyMetrics:
    """
    Compute all accuracy metrics for a (sub)set of the joined DataFrame.

    MAPE fix: computed over non-zero actuals only. The number of excluded
    zero-actual intervals is reported in mape_zero_exclusions so callers
    can present this information rather than silently dropping coverage.

    Parameters
    ----------
    joined_df          : Output of join_and_compute_errors().
    period_label       : e.g. "January 2026" or "2026-01-15".
    n_total_intervals  : Expected delivery hours for the period (24 × days).
    """
    n_matched = len(joined_df)

    _empty = AccuracyMetrics(
        period_label=period_label,
        n_matched_intervals=0,
        n_total_intervals=n_total_intervals,
        coverage_pct=0.0,
        mae_mw=0.0, rmse_mw=0.0, mbe_mw=0.0,
        mape_pct=None, mape_zero_exclusions=0,
        nmae_pct=0.0,
        mean_actual_mw=0.0, mean_forecast_mw=0.0, mean_lead_hours=0.0,
        over_forecast_count=0, under_forecast_count=0,
        over_forecast_pct=0.0, under_forecast_pct=0.0,
        max_over_forecast_mw=0.0, max_under_forecast_mw=0.0,
    )

    if n_matched == 0:
        logger.warning("compute_metrics: no matched intervals for '%s'", period_label)
        return _empty

    mae  = float(joined_df["abs_error_mw"].mean())
    rmse = float(np.sqrt(joined_df["sq_error_mw2"].mean()))
    mbe  = float(joined_df["error_mw"].mean())

    mean_actual   = float(joined_df["actual_mw"].mean())
    mean_forecast = float(joined_df["forecast_mw"].mean())
    mean_lead     = float(joined_df["lead_hours"].mean())

    # ── MAPE: computed over non-zero actuals only ────────────────────────
    # Formula: mean(|error_i / actual_i|) × 100  for all i where actual_i ≠ 0
    # Zero-actual periods are excluded and the exclusion count is reported.
    zero_actual_mask    = joined_df["actual_mw"] == 0
    n_zero_actual       = int(zero_actual_mask.sum())
    nonzero_pct_errors  = joined_df.loc[~zero_actual_mask, "pct_error"].dropna()

    if nonzero_pct_errors.empty:
        mape: Optional[float] = None
        logger.warning(
            "compute_metrics: MAPE undefined for '%s' — all actuals are zero", period_label
        )
    else:
        mape = float(nonzero_pct_errors.abs().mean())
        if n_zero_actual > 0:
            logger.info(
                "compute_metrics: MAPE for '%s' computed over %d/%d intervals "
                "(%d zero-actual intervals excluded)",
                period_label,
                len(nonzero_pct_errors),
                n_matched,
                n_zero_actual,
            )

    # ── nMAE ─────────────────────────────────────────────────────────────
    nmae = (mae / mean_actual * 100.0) if mean_actual > 0 else 0.0

    # ── Coverage ─────────────────────────────────────────────────────────
    coverage = (n_matched / n_total_intervals * 100.0) if n_total_intervals > 0 else 0.0

    # ── Over/under forecast counts ───────────────────────────────────────
    over_mask  = joined_df["error_mw"] > 0
    under_mask = joined_df["error_mw"] < 0
    n_over     = int(over_mask.sum())
    n_under    = int(under_mask.sum())
    n_exact    = n_matched - n_over - n_under  # exact match (error == 0, rare)

    max_over  = float(joined_df.loc[over_mask,  "error_mw"].max()) if n_over  > 0 else 0.0
    max_under = float(joined_df.loc[under_mask, "error_mw"].abs().max()) if n_under > 0 else 0.0

    return AccuracyMetrics(
        period_label=period_label,
        n_matched_intervals=n_matched,
        n_total_intervals=n_total_intervals,
        coverage_pct=round(coverage, 2),
        mae_mw=round(mae, 2),
        rmse_mw=round(rmse, 2),
        mbe_mw=round(mbe, 2),
        mape_pct=round(mape, 2) if mape is not None else None,
        mape_zero_exclusions=n_zero_actual,
        nmae_pct=round(nmae, 2),
        mean_actual_mw=round(mean_actual, 2),
        mean_forecast_mw=round(mean_forecast, 2),
        mean_lead_hours=round(mean_lead, 2),
        over_forecast_count=n_over,
        under_forecast_count=n_under,
        over_forecast_pct=round(n_over / n_matched * 100, 2),
        under_forecast_pct=round(n_under / n_matched * 100, 2),
        max_over_forecast_mw=round(max_over, 2),
        max_under_forecast_mw=round(max_under, 2),
    )


def compute_daily_metrics(joined_df: pd.DataFrame) -> list[dict]:
    """
    Per-day accuracy metrics.

    Each dict corresponds to one settlement_date and is converted to
    a DailyMetrics Pydantic model in the router layer.
    """
    if joined_df.empty:
        return []

    grouped = (
        joined_df
        .groupby("settlement_date")
        .agg(
            n_intervals   =("start_time",   "count"),
            mean_forecast =("forecast_mw",  "mean"),
            mean_actual   =("actual_mw",    "mean"),
            mae           =("abs_error_mw", "mean"),
            mbe           =("error_mw",     "mean"),
            rmse_sq       =("sq_error_mw2", "mean"),
        )
        .reset_index()
    )
    grouped["rmse"] = np.sqrt(grouped["rmse_sq"])

    records = []
    for _, row in grouped.iterrows():
        records.append({
            "settlement_date":  row["settlement_date"],
            "n_intervals":      int(row["n_intervals"]),
            "mean_forecast_mw": round(float(row["mean_forecast"]), 2),
            "mean_actual_mw":   round(float(row["mean_actual"]), 2),
            "mae_mw":           round(float(row["mae"]), 2),
            "mbe_mw":           round(float(row["mbe"]), 2),
            "rmse_mw":          round(float(row["rmse"]), 2),
        })
    return records


def compute_horizon_metrics(joined_df: pd.DataFrame) -> list[dict]:
    """
    Accuracy metrics grouped by forecast lead time.

    The day-ahead procurement window (24–36h lead) is the most relevant
    for the target use case. Additional buckets provide context.
    """
    if joined_df.empty:
        return []

    records = []
    for label, lo, hi in HORIZON_BUCKETS:
        bucket = joined_df[
            (joined_df["lead_hours"] >= lo) & (joined_df["lead_hours"] < hi)
        ]
        if bucket.empty:
            continue
        records.append({
            "bucket_label":   label,
            "lead_hours_min": lo,
            "lead_hours_max": hi if hi < 9999 else 999,
            "n_intervals":    int(len(bucket)),
            "mae_mw":         round(float(bucket["abs_error_mw"].mean()), 2),
            "mbe_mw":         round(float(bucket["error_mw"].mean()), 2),
            "rmse_mw":        round(float(np.sqrt(bucket["sq_error_mw2"].mean())), 2),
        })
    return records


def compute_error_distribution(joined_df: pd.DataFrame, n_bins: int = 20) -> dict:
    """
    Histogram of forecast errors (error_mw = forecast − actual).

    Returns bin counts, mean, and std dev. The histogram is symmetric
    around zero when forecasts are unbiased.
    """
    if joined_df.empty:
        return {"bins": [], "mean_error_mw": 0.0, "std_error_mw": 0.0, "total_intervals": 0}

    errors = joined_df["error_mw"].dropna()
    total  = len(errors)
    mean_e = float(errors.mean())
    std_e  = float(errors.std(ddof=1))   # sample std dev (ddof=1), consistent with reporting

    counts, bin_edges = np.histogram(errors, bins=n_bins)
    bins = []
    for i, count in enumerate(counts):
        lo = float(bin_edges[i])
        hi = float(bin_edges[i + 1])
        bins.append({
            "bin_label":    f"{lo:.0f} to {hi:.0f}",
            "bin_min_mw":   round(lo, 1),
            "bin_max_mw":   round(hi, 1),
            "count":        int(count),
            "pct_of_total": round(int(count) / total * 100, 2) if total > 0 else 0.0,
        })

    return {
        "total_intervals": total,
        "bins":            bins,
        "mean_error_mw":   round(mean_e, 2),
        "std_error_mw":    round(std_e, 2),
    }


def compute_time_of_day_metrics(joined_df: pd.DataFrame) -> list[dict]:
    """
    Accuracy metrics grouped by delivery hour of day (0–23 UTC).

    Reveals whether forecast performance degrades at certain hours
    (e.g. nocturnal ramp-ups or morning peaks).

    Returns one dict per hour that has at least one matched interval.
    """
    if joined_df.empty:
        return []

    df = joined_df.copy()
    df["hour_of_day"] = df["start_time"].dt.hour

    grouped = (
        df.groupby("hour_of_day")
        .agg(
            n_intervals   =("start_time",   "count"),
            mean_forecast =("forecast_mw",  "mean"),
            mean_actual   =("actual_mw",    "mean"),
            mae           =("abs_error_mw", "mean"),
            mbe           =("error_mw",     "mean"),
            rmse_sq       =("sq_error_mw2", "mean"),
        )
        .reset_index()
    )
    grouped["rmse"] = np.sqrt(grouped["rmse_sq"])

    records = []
    for _, row in grouped.iterrows():
        records.append({
            "hour_of_day":    int(row["hour_of_day"]),
            "hour_label":     f"{int(row['hour_of_day']):02d}:00",
            "n_intervals":    int(row["n_intervals"]),
            "mean_forecast_mw": round(float(row["mean_forecast"]), 2),
            "mean_actual_mw":   round(float(row["mean_actual"]), 2),
            "mae_mw":           round(float(row["mae"]), 2),
            "mbe_mw":           round(float(row["mbe"]), 2),
            "rmse_mw":          round(float(row["rmse"]), 2),
        })
    return records


def compute_forecast_revision_analysis(
    forecasts_df: pd.DataFrame,
    joined_df: pd.DataFrame,
) -> list[dict]:
    """
    For each delivery hour, compare the decision forecast (used at cutoff)
    with the first available forecast (earliest publish_time) for that hour.

    Reveals how much forecasts changed between first publication and the
    day-ahead decision point.

    Parameters
    ----------
    forecasts_df : pd.DataFrame
        Full cleaned WINDFOR DataFrame (all vintages, hindcasts removed).
    joined_df : pd.DataFrame
        Output of join_and_compute_errors().

    Returns
    -------
    list[dict] — one entry per delivery hour in joined_df.
    """
    if forecasts_df.empty or joined_df.empty:
        return []

    # First vintage per delivery hour (earliest publish_time)
    first_vintage = (
        forecasts_df
        .sort_values("publish_time")
        .groupby("start_time")
        .first()
        .reset_index()
        .rename(columns={
            "generation_mw": "first_forecast_mw",
            "publish_time":  "first_publish_time",
            "lead_hours":    "first_lead_hours",
        })
    )

    # Merge with joined_df to get decision forecast and actual
    merged = joined_df[["start_time", "forecast_mw", "forecast_publish_time",
                         "actual_mw", "error_mw"]].merge(
        first_vintage[["start_time", "first_forecast_mw", "first_publish_time"]],
        on="start_time",
        how="left",
    )

    merged["revision_mw"] = merged["forecast_mw"] - merged["first_forecast_mw"]
    merged["first_error_mw"] = merged["first_forecast_mw"] - merged["actual_mw"]

    records = []
    for _, row in merged.iterrows():
        records.append({
            "start_time":            row["start_time"].isoformat(),
            "first_forecast_mw":     round(float(row["first_forecast_mw"]), 2) if not math.isnan(row["first_forecast_mw"]) else None,
            "first_publish_time":    row["first_publish_time"].isoformat() if pd.notna(row["first_publish_time"]) else None,
            "decision_forecast_mw":  round(float(row["forecast_mw"]), 2),
            "decision_publish_time": row["forecast_publish_time"].isoformat(),
            "revision_mw":           round(float(row["revision_mw"]), 2) if not math.isnan(row["revision_mw"]) else None,
            "actual_mw":             round(float(row["actual_mw"]), 2),
            "decision_error_mw":     round(float(row["error_mw"]), 2),
            "first_error_mw":        round(float(row["first_error_mw"]), 2) if not math.isnan(row["first_error_mw"]) else None,
        })
    return records


def generate_business_insights(
    joined_df: pd.DataFrame,
    metrics: AccuracyMetrics,
    daily_metrics: list[dict],
    time_of_day_metrics: list[dict],
) -> list[dict]:
    """
    Generate data-driven business insights for the procurement team.

    IMPORTANT: Every insight is derived from calculated metrics.
    No insight is generated unless the underlying data supports it.
    Consumer demand data is NOT available; insights are scoped to
    wind generation forecast uncertainty only.

    Returns a list of insight dicts with keys:
      category, severity, title, body, supporting_data
    """
    insights: list[dict] = []

    if joined_df.empty or metrics.n_matched_intervals == 0:
        return insights

    # ── Insight 1: systematic bias ───────────────────────────────────────
    bias_threshold_mw = 200  # MW — below this, bias is not operationally meaningful
    if abs(metrics.mbe_mw) >= bias_threshold_mw:
        direction = "overestimated" if metrics.mbe_mw > 0 else "underestimated"
        procurement_impact = (
            "Consistently overestimating wind generation means procurement plans "
            "assumed more renewable supply than was actually delivered."
            if metrics.mbe_mw > 0 else
            "Consistently underestimating wind generation means procurement plans "
            "assumed less renewable supply than was actually delivered."
        )
        insights.append({
            "category": "Systematic Bias",
            "severity": "high" if abs(metrics.mbe_mw) > 500 else "medium",
            "title": f"Forecasts systematically {direction} wind generation",
            "body": (
                f"The mean bias error (MBE) across {metrics.n_matched_intervals} matched intervals "
                f"was {metrics.mbe_mw:+.0f} MW ({direction}). "
                f"{procurement_impact}"
            ),
            "supporting_data": {
                "mbe_mw": metrics.mbe_mw,
                "n_intervals": metrics.n_matched_intervals,
            },
        })

    # ── Insight 2: over vs under forecast dominance ─────────────────────
    if metrics.over_forecast_pct > 60:
        insights.append({
            "category": "Forecast Direction",
            "severity": "medium",
            "title": f"Forecasts exceeded actuals in {metrics.over_forecast_pct:.1f}% of intervals",
            "body": (
                f"Wind generation was lower than the day-ahead forecast in "
                f"{metrics.over_forecast_count} of {metrics.n_matched_intervals} delivery hours "
                f"({metrics.over_forecast_pct:.1f}%). This directional pattern indicates the "
                f"forecast model tended to predict more wind than materialised."
            ),
            "supporting_data": {
                "over_forecast_count": metrics.over_forecast_count,
                "over_forecast_pct": metrics.over_forecast_pct,
            },
        })
    elif metrics.under_forecast_pct > 60:
        insights.append({
            "category": "Forecast Direction",
            "severity": "medium",
            "title": f"Actuals exceeded forecasts in {metrics.under_forecast_pct:.1f}% of intervals",
            "body": (
                f"Wind generation was higher than the day-ahead forecast in "
                f"{metrics.under_forecast_count} of {metrics.n_matched_intervals} delivery hours "
                f"({metrics.under_forecast_pct:.1f}%). This indicates the forecast model "
                f"tended to underpredict available wind resource."
            ),
            "supporting_data": {
                "under_forecast_count": metrics.under_forecast_count,
                "under_forecast_pct": metrics.under_forecast_pct,
            },
        })

    # ── Insight 3: outlier hours (RMSE >> MAE) ──────────────────────────
    if metrics.rmse_mw > 0 and metrics.mae_mw > 0:
        rmse_to_mae = metrics.rmse_mw / metrics.mae_mw
        if rmse_to_mae > 1.5:
            insights.append({
                "category": "Error Distribution",
                "severity": "medium",
                "title": "A small number of delivery hours had very large forecast errors",
                "body": (
                    f"RMSE ({metrics.rmse_mw:.0f} MW) is {rmse_to_mae:.1f}× larger than MAE "
                    f"({metrics.mae_mw:.0f} MW). This ratio indicates the forecast error "
                    f"distribution has heavy tails — a small number of delivery hours "
                    f"experienced disproportionately large errors. The worst overforecast "
                    f"was {metrics.max_over_forecast_mw:.0f} MW; "
                    f"the worst underforecast was {metrics.max_under_forecast_mw:.0f} MW."
                ),
                "supporting_data": {
                    "mae_mw": metrics.mae_mw,
                    "rmse_mw": metrics.rmse_mw,
                    "rmse_to_mae_ratio": round(rmse_to_mae, 2),
                    "max_over_forecast_mw": metrics.max_over_forecast_mw,
                    "max_under_forecast_mw": metrics.max_under_forecast_mw,
                },
            })

    # ── Insight 4: worst day ─────────────────────────────────────────────
    if daily_metrics:
        worst_day = max(daily_metrics, key=lambda d: d["mae_mw"])
        best_day  = min(daily_metrics, key=lambda d: d["mae_mw"])
        if worst_day["mae_mw"] > metrics.mae_mw * 1.5:
            insights.append({
                "category": "Daily Performance",
                "severity": "low",
                "title": f"Forecast accuracy varied significantly by day",
                "body": (
                    f"The worst-performing day was {worst_day['settlement_date']} "
                    f"(MAE {worst_day['mae_mw']:.0f} MW), "
                    f"and the best was {best_day['settlement_date']} "
                    f"(MAE {best_day['mae_mw']:.0f} MW). "
                    f"The monthly average MAE was {metrics.mae_mw:.0f} MW."
                ),
                "supporting_data": {
                    "worst_date": str(worst_day["settlement_date"]),
                    "worst_mae_mw": worst_day["mae_mw"],
                    "best_date": str(best_day["settlement_date"]),
                    "best_mae_mw": best_day["mae_mw"],
                    "monthly_mae_mw": metrics.mae_mw,
                },
            })

    # ── Insight 5: time-of-day pattern ───────────────────────────────────
    if len(time_of_day_metrics) >= 12:
        tod_sorted = sorted(time_of_day_metrics, key=lambda h: h["mae_mw"])
        worst_hour = tod_sorted[-1]
        best_hour  = tod_sorted[0]
        if worst_hour["mae_mw"] > best_hour["mae_mw"] * 1.4:
            insights.append({
                "category": "Time-of-Day Pattern",
                "severity": "low",
                "title": f"Forecast errors were higher at {worst_hour['hour_label']} UTC",
                "body": (
                    f"Delivery hour {worst_hour['hour_label']} UTC had the highest "
                    f"average absolute error (MAE {worst_hour['mae_mw']:.0f} MW "
                    f"over {worst_hour['n_intervals']} days), compared to "
                    f"{best_hour['hour_label']} UTC which had the lowest "
                    f"(MAE {best_hour['mae_mw']:.0f} MW). "
                    f"This may reflect diurnal wind patterns that are harder to forecast."
                ),
                "supporting_data": {
                    "worst_hour": worst_hour["hour_label"],
                    "worst_hour_mae_mw": worst_hour["mae_mw"],
                    "best_hour": best_hour["hour_label"],
                    "best_hour_mae_mw": best_hour["mae_mw"],
                },
            })

    # ── Insight 6: data coverage ─────────────────────────────────────────
    if metrics.coverage_pct < 95:
        insights.append({
            "category": "Data Coverage",
            "severity": "high",
            "title": f"Incomplete forecast coverage — {100 - metrics.coverage_pct:.1f}% of hours unmatched",
            "body": (
                f"Only {metrics.n_matched_intervals} of {metrics.n_total_intervals} expected "
                f"delivery hours ({metrics.coverage_pct:.1f}%) had both a day-ahead forecast "
                f"and an actual generation value. Metrics are computed over matched intervals only. "
                f"Missing coverage reduces confidence in the reported accuracy figures."
            ),
            "supporting_data": {
                "matched": metrics.n_matched_intervals,
                "total": metrics.n_total_intervals,
                "coverage_pct": metrics.coverage_pct,
            },
        })

    # ── Demand disclaimer (always included) ─────────────────────────────
    insights.append({
        "category": "Scope Limitation",
        "severity": "info",
        "title": "Wind generation uncertainty only — not an electricity procurement quantity",
        "body": (
            "Consumer demand data is not available in this application. "
            "The metrics shown quantify how accurately day-ahead wind generation forecasts "
            "predicted actual wind output. They do not represent the quantity of electricity "
            "the procurement team should buy or the residual demand to be sourced from "
            "other market products. Use these metrics alongside demand forecasts to "
            "determine the net electricity procurement requirement."
        ),
        "supporting_data": {},
    })

    return insights


# ── Internal helpers ─────────────────────────────────────────────────────────

def _assert_utc_aware(series: pd.Series, label: str) -> None:
    """Raise ValueError if the datetime series is not UTC-aware."""
    if series.empty:
        return
    if getattr(series.dtype, "tz", None) is None:
        raise ValueError(
            f"{label} must be timezone-aware UTC datetimes. "
            "Got timezone-naive series. This indicates a data ingestion bug."
        )


def _empty_joined_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "start_time", "settlement_date", "settlement_period",
        "forecast_mw", "actual_mw", "actual_publish_time",
        "forecast_publish_time", "lead_hours", "cutoff_hour",
        "error_mw", "abs_error_mw", "sq_error_mw2", "pct_error",
    ])
