"""
Unit tests for accuracy_service.py

Tests verify:
  - Correct formula implementation for MAE, RMSE, MBE, MAPE, nMAE
  - MAPE zero-exclusion logic
  - Error sign convention (positive = overforecast)
  - Over/under forecast counting
  - Empty DataFrame handling
  - UTC timezone enforcement
  - join_and_compute_errors column correctness
"""

from __future__ import annotations

import math
from datetime import date, timezone

import numpy as np
import pandas as pd
import pytest

from app.accuracy_service import (
    compute_metrics,
    join_and_compute_errors,
    compute_daily_metrics,
    compute_time_of_day_metrics,
)

UTC = timezone.utc


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_actuals(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal actuals DataFrame matching actuals_service output schema."""
    df = pd.DataFrame(rows)
    df["start_time"]    = pd.to_datetime(df["start_time"], utc=True)
    df["publish_time"]  = pd.to_datetime(df["publish_time"], utc=True)
    df["settlement_date"] = pd.to_datetime(df["settlement_date"]).dt.date
    df["settlement_period"] = df["settlement_period"].astype("int64")
    df["generation_mw"] = df["generation_mw"].astype(float)
    df["is_on_hour"]    = df["start_time"].dt.minute == 0
    return df


def _make_decisions(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal decision forecasts DataFrame."""
    df = pd.DataFrame(rows)
    df["start_time"]              = pd.to_datetime(df["start_time"], utc=True)
    df["forecast_publish_time"]   = pd.to_datetime(df["forecast_publish_time"], utc=True)
    df["forecast_mw"]             = df["forecast_mw"].astype(float)
    df["lead_hours"]              = df["lead_hours"].astype(float)
    df["cutoff_hour"]             = df.get("cutoff_hour", 9)
    return df


# ── join_and_compute_errors ───────────────────────────────────────────────────

class TestJoinAndComputeErrors:

    def test_basic_join_produces_error_columns(self):
        actuals = _make_actuals([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-15T10:30:00Z",
             "settlement_date": "2026-01-15", "settlement_period": 21,
             "generation_mw": 8000, "fuel_type": "WIND"},
        ])
        decisions = _make_decisions([
            {"start_time": "2026-01-15T10:00:00Z", "forecast_publish_time": "2026-01-14T09:00:00Z",
             "forecast_mw": 9500, "lead_hours": 25.0},
        ])
        joined = join_and_compute_errors(actuals, decisions)

        assert len(joined) == 1
        assert joined["error_mw"].iloc[0] == pytest.approx(1500.0)        # 9500 - 8000
        assert joined["abs_error_mw"].iloc[0] == pytest.approx(1500.0)
        assert joined["sq_error_mw2"].iloc[0] == pytest.approx(1500.0 ** 2)
        assert joined["pct_error"].iloc[0] == pytest.approx((1500.0 / 8000.0) * 100)

    def test_hh30_actuals_excluded_from_join(self):
        """HH:30 settlement periods must NOT appear in the join output."""
        actuals = _make_actuals([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-15T10:30:00Z",
             "settlement_date": "2026-01-15", "settlement_period": 21,
             "generation_mw": 8000, "fuel_type": "WIND"},
            {"start_time": "2026-01-15T10:30:00Z", "publish_time": "2026-01-15T11:00:00Z",
             "settlement_date": "2026-01-15", "settlement_period": 22,
             "generation_mw": 8200, "fuel_type": "WIND"},  # HH:30 — must be excluded
        ])
        decisions = _make_decisions([
            {"start_time": "2026-01-15T10:00:00Z", "forecast_publish_time": "2026-01-14T09:00:00Z",
             "forecast_mw": 9000, "lead_hours": 25.0},
        ])
        joined = join_and_compute_errors(actuals, decisions)
        assert len(joined) == 1
        assert joined["start_time"].iloc[0].minute == 0

    def test_pct_error_nan_when_actual_zero(self):
        actuals = _make_actuals([
            {"start_time": "2026-01-15T02:00:00Z", "publish_time": "2026-01-15T02:30:00Z",
             "settlement_date": "2026-01-15", "settlement_period": 5,
             "generation_mw": 0, "fuel_type": "WIND"},
        ])
        decisions = _make_decisions([
            {"start_time": "2026-01-15T02:00:00Z", "forecast_publish_time": "2026-01-14T09:00:00Z",
             "forecast_mw": 500, "lead_hours": 17.0},
        ])
        joined = join_and_compute_errors(actuals, decisions)
        assert len(joined) == 1
        assert math.isnan(joined["pct_error"].iloc[0])

    def test_negative_error_when_underforecast(self):
        """forecast < actual → error_mw negative."""
        actuals = _make_actuals([
            {"start_time": "2026-01-20T14:00:00Z", "publish_time": "2026-01-20T14:30:00Z",
             "settlement_date": "2026-01-20", "settlement_period": 29,
             "generation_mw": 12000, "fuel_type": "WIND"},
        ])
        decisions = _make_decisions([
            {"start_time": "2026-01-20T14:00:00Z", "forecast_publish_time": "2026-01-19T09:00:00Z",
             "forecast_mw": 10000, "lead_hours": 29.0},
        ])
        joined = join_and_compute_errors(actuals, decisions)
        assert joined["error_mw"].iloc[0] == pytest.approx(-2000.0)

    def test_empty_actuals_returns_empty(self):
        decisions = _make_decisions([
            {"start_time": "2026-01-15T10:00:00Z", "forecast_publish_time": "2026-01-14T09:00:00Z",
             "forecast_mw": 9000, "lead_hours": 25.0},
        ])
        result = join_and_compute_errors(pd.DataFrame(), decisions)
        assert result.empty

    def test_empty_decisions_returns_empty(self):
        actuals = _make_actuals([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-15T10:30:00Z",
             "settlement_date": "2026-01-15", "settlement_period": 21,
             "generation_mw": 8000, "fuel_type": "WIND"},
        ])
        result = join_and_compute_errors(actuals, pd.DataFrame())
        assert result.empty


# ── compute_metrics ───────────────────────────────────────────────────────────

class TestComputeMetrics:

    def _joined(self, pairs: list[tuple[float, float]]) -> pd.DataFrame:
        """Build a joined_df from (forecast, actual) pairs for a fixed date."""
        rows = []
        for i, (f, a) in enumerate(pairs):
            rows.append({
                "start_time":            pd.Timestamp(f"2026-01-15T{i:02d}:00:00Z"),
                "settlement_date":       date(2026, 1, 15),
                "settlement_period":     i * 2 + 1,
                "forecast_mw":           float(f),
                "actual_mw":             float(a),
                "actual_publish_time":   pd.Timestamp(f"2026-01-15T{i:02d}:30:00Z"),
                "forecast_publish_time": pd.Timestamp(f"2026-01-14T09:00:00Z"),
                "lead_hours":            27.0,
                "cutoff_hour":           9,
            })
        df = pd.DataFrame(rows)
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        df["actual_publish_time"] = pd.to_datetime(df["actual_publish_time"], utc=True)
        df["forecast_publish_time"] = pd.to_datetime(df["forecast_publish_time"], utc=True)
        df["error_mw"]     = df["forecast_mw"] - df["actual_mw"]
        df["abs_error_mw"] = df["error_mw"].abs()
        df["sq_error_mw2"] = df["error_mw"] ** 2
        df["pct_error"] = np.where(df["actual_mw"] != 0,
                                    df["error_mw"] / df["actual_mw"] * 100, np.nan)
        return df

    def test_mae_formula(self):
        # errors: +1000, -500, +300  → |1000|+|500|+|300| / 3 = 600
        df = self._joined([(11000, 10000), (9500, 10000), (10300, 10000)])
        m = compute_metrics(df, "test", 3)
        assert m.mae_mw == pytest.approx(600.0, abs=0.01)

    def test_rmse_formula(self):
        # (1000²+500²+300²)/3 = (1000000+250000+90000)/3 = 1340000/3 → sqrt = 668.33
        df = self._joined([(11000, 10000), (9500, 10000), (10300, 10000)])
        m = compute_metrics(df, "test", 3)
        expected = math.sqrt((1000**2 + 500**2 + 300**2) / 3)
        assert m.rmse_mw == pytest.approx(expected, abs=0.01)

    def test_mbe_positive_when_overforecast(self):
        # All forecasts > actual → MBE positive
        df = self._joined([(11000, 10000), (11000, 10000)])
        m = compute_metrics(df, "test", 2)
        assert m.mbe_mw == pytest.approx(1000.0, abs=0.01)

    def test_mbe_negative_when_underforecast(self):
        df = self._joined([(9000, 10000), (9000, 10000)])
        m = compute_metrics(df, "test", 2)
        assert m.mbe_mw == pytest.approx(-1000.0, abs=0.01)

    def test_mbe_near_zero_when_balanced(self):
        df = self._joined([(11000, 10000), (9000, 10000)])
        m = compute_metrics(df, "test", 2)
        assert abs(m.mbe_mw) < 0.01

    def test_mape_excludes_zero_actuals_and_reports_exclusion(self):
        # 3 intervals: actual=[10000, 0, 8000], forecast=[11000, 500, 9000]
        # Only intervals 0 and 2 contribute: |1000/10000|*100=10, |1000/8000|*100=12.5
        # MAPE = (10 + 12.5) / 2 = 11.25
        df = self._joined([(11000, 10000), (500, 0), (9000, 8000)])
        m = compute_metrics(df, "test", 3)
        assert m.mape_zero_exclusions == 1
        assert m.mape_pct == pytest.approx(11.25, abs=0.01)

    def test_mape_none_when_all_actuals_zero(self):
        df = self._joined([(500, 0), (200, 0)])
        m = compute_metrics(df, "test", 2)
        assert m.mape_pct is None
        assert m.mape_zero_exclusions == 2

    def test_nmae_formula(self):
        # errors: 1000, -500 → MAE=750, mean_actual=10000 → nMAE=7.5%
        df = self._joined([(11000, 10000), (9500, 10000)])
        m = compute_metrics(df, "test", 2)
        assert m.nmae_pct == pytest.approx(7.5, abs=0.01)

    def test_coverage_pct(self):
        df = self._joined([(11000, 10000)] * 3)
        m = compute_metrics(df, "test", n_total_intervals=10)
        assert m.coverage_pct == pytest.approx(30.0, abs=0.01)

    def test_over_under_counts(self):
        # 2 over (error>0), 1 under (error<0), 1 exact (error==0)
        df = self._joined([
            (11000, 10000),  # over +1000
            (11000, 10000),  # over +1000
            (9000, 10000),   # under -1000
            (10000, 10000),  # exact 0
        ])
        m = compute_metrics(df, "test", 4)
        assert m.over_forecast_count == 2
        assert m.under_forecast_count == 1
        assert m.over_forecast_pct == pytest.approx(50.0, abs=0.01)

    def test_max_over_under_forecast(self):
        df = self._joined([
            (13000, 10000),  # over +3000 — largest
            (11000, 10000),  # over +1000
            (7000, 10000),   # under -3000 — largest
        ])
        m = compute_metrics(df, "test", 3)
        assert m.max_over_forecast_mw == pytest.approx(3000.0, abs=0.01)
        assert m.max_under_forecast_mw == pytest.approx(3000.0, abs=0.01)

    def test_empty_df_returns_zero_metrics(self):
        m = compute_metrics(pd.DataFrame(), "test", 10)
        assert m.mae_mw == 0.0
        assert m.rmse_mw == 0.0
        assert m.mbe_mw == 0.0
        assert m.n_matched_intervals == 0
        assert m.coverage_pct == 0.0

    def test_rmse_always_gte_mae(self):
        """RMSE ≥ MAE always holds (Cauchy–Schwarz inequality)."""
        import random
        random.seed(42)
        # Use 24 pairs maximum so hour index stays within 0–23
        pairs = [(random.uniform(5000, 20000), random.uniform(5000, 20000)) for _ in range(24)]
        df = self._joined(pairs)
        m = compute_metrics(df, "test", 24)
        assert m.rmse_mw >= m.mae_mw - 0.01  # small tolerance for float rounding


# ── compute_daily_metrics ─────────────────────────────────────────────────────

class TestComputeDailyMetrics:

    def test_groups_by_settlement_date(self):
        rows = []
        for day in [15, 16]:
            for hour in range(3):
                rows.append({
                    "start_time":            pd.Timestamp(f"2026-01-{day:02d}T{hour:02d}:00:00Z"),
                    "settlement_date":       date(2026, 1, day),
                    "settlement_period":     hour * 2 + 1,
                    "forecast_mw":           10000.0 + hour * 100,
                    "actual_mw":             10000.0,
                    "actual_publish_time":   pd.Timestamp(f"2026-01-{day:02d}T{hour:02d}:30:00Z"),
                    "forecast_publish_time": pd.Timestamp("2026-01-14T09:00:00Z"),
                    "lead_hours":            27.0,
                    "cutoff_hour":           9,
                    "error_mw":              float(hour * 100),
                    "abs_error_mw":          float(hour * 100),
                    "sq_error_mw2":          float((hour * 100) ** 2),
                    "pct_error":             float(hour),
                })
        df = pd.DataFrame(rows)
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        df["actual_publish_time"] = pd.to_datetime(df["actual_publish_time"], utc=True)
        df["forecast_publish_time"] = pd.to_datetime(df["forecast_publish_time"], utc=True)

        result = compute_daily_metrics(df)
        assert len(result) == 2
        dates = [r["settlement_date"] for r in result]
        assert date(2026, 1, 15) in dates
        assert date(2026, 1, 16) in dates

    def test_empty_returns_empty(self):
        assert compute_daily_metrics(pd.DataFrame()) == []


# ── compute_time_of_day_metrics ───────────────────────────────────────────────

class TestTimeOfDayMetrics:

    def test_groups_by_hour(self):
        rows = []
        for day in range(1, 4):
            for hour in [9, 14, 20]:
                rows.append({
                    "start_time":            pd.Timestamp(f"2026-01-{day:02d}T{hour:02d}:00:00Z"),
                    "settlement_date":       date(2026, 1, day),
                    "settlement_period":     hour * 2 + 1,
                    "forecast_mw":           float(10000 + hour * 50),
                    "actual_mw":             10000.0,
                    "actual_publish_time":   pd.Timestamp(f"2026-01-{day:02d}T{hour:02d}:30:00Z"),
                    "forecast_publish_time": pd.Timestamp("2026-01-14T09:00:00Z"),
                    "lead_hours":            27.0,
                    "cutoff_hour":           9,
                    "error_mw":              float(hour * 50),
                    "abs_error_mw":          float(hour * 50),
                    "sq_error_mw2":          float((hour * 50) ** 2),
                    "pct_error":             float(hour * 0.5),
                })
        df = pd.DataFrame(rows)
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        df["actual_publish_time"] = pd.to_datetime(df["actual_publish_time"], utc=True)
        df["forecast_publish_time"] = pd.to_datetime(df["forecast_publish_time"], utc=True)

        result = compute_time_of_day_metrics(df)
        assert len(result) == 3
        hours = {r["hour_of_day"] for r in result}
        assert hours == {9, 14, 20}

    def test_empty_returns_empty(self):
        assert compute_time_of_day_metrics(pd.DataFrame()) == []
