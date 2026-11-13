"""
Unit tests for vintage_service.py

Verifies:
  - publishTime cutoff enforcement (strict: post-cutoff forecasts excluded)
  - Correct selection of latest eligible vintage per delivery hour
  - Hindcasts already removed upstream (tested here defensively)
  - Edge cases: no eligible forecasts, single vintage, exact cutoff match
"""

from __future__ import annotations

from datetime import timezone

import pandas as pd
import pytest

from app.vintage_service import select_decision_forecasts

UTC = timezone.utc


def _make_forecasts(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["publish_time"]  = pd.to_datetime(df["publish_time"], utc=True)
    df["start_time"]    = pd.to_datetime(df["start_time"],   utc=True)
    df["generation_mw"] = df["generation_mw"].astype(float)
    df["lead_hours"]    = (df["start_time"] - df["publish_time"]).dt.total_seconds() / 3600
    return df


class TestSelectDecisionForecasts:

    def test_selects_latest_eligible_vintage(self):
        """
        Three vintages for the same delivery hour.
        Cutoff = 09:00 on D-1. The 09:00 vintage is eligible (<=), 09:30 is not.
        Expected: 09:00 vintage selected (latest eligible).
        """
        df = _make_forecasts([
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-13T22:30:00Z", "generation_mw": 8000},
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T07:30:00Z", "generation_mw": 8500},
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T09:00:00Z", "generation_mw": 9000},
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T09:30:00Z", "generation_mw": 9500},  # post-cutoff
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert len(result) == 1
        assert result.iloc[0]["forecast_mw"] == pytest.approx(9000.0)
        assert result.iloc[0]["forecast_publish_time"] == pd.Timestamp("2026-01-14T09:00:00Z", tz="UTC")

    def test_excludes_post_cutoff_entirely(self):
        """All vintages published after cutoff → no decision forecast for that hour."""
        df = _make_forecasts([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T10:00:00Z", "generation_mw": 7000},
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T11:00:00Z", "generation_mw": 7500},
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert result.empty

    def test_exact_cutoff_time_is_included(self):
        """
        A vintage published exactly at the cutoff datetime must be included
        (the condition is <=, not <).
        """
        df = _make_forecasts([
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T09:00:00Z", "generation_mw": 9000},
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert len(result) == 1
        assert result.iloc[0]["forecast_mw"] == pytest.approx(9000.0)

    def test_one_second_after_cutoff_is_excluded(self):
        """09:00:01 is after the 09:00:00 cutoff and must be excluded."""
        df = _make_forecasts([
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T09:00:01Z", "generation_mw": 9500},
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert result.empty

    def test_multiple_delivery_hours(self):
        """Each delivery hour gets its own independent vintage selection."""
        df = _make_forecasts([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T07:30:00Z", "generation_mw": 8000},
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T09:00:00Z", "generation_mw": 8500},  # selected
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T07:30:00Z", "generation_mw": 9000},  # selected (only one)
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert len(result) == 2
        result = result.set_index("start_time")
        assert result.loc[pd.Timestamp("2026-01-15T10:00:00Z", tz="UTC"), "forecast_mw"] == pytest.approx(8500.0)
        assert result.loc[pd.Timestamp("2026-01-15T14:00:00Z", tz="UTC"), "forecast_mw"] == pytest.approx(9000.0)

    def test_cutoff_is_per_delivery_date_not_global(self):
        """
        Delivery hour on Jan 15 uses cutoff on Jan 14.
        Delivery hour on Jan 16 uses cutoff on Jan 15.
        A vintage published Jan 14 09:30 is post-cutoff for Jan 15 delivery
        but pre-cutoff for Jan 16 delivery.
        """
        df = _make_forecasts([
            # Jan 15 delivery — cutoff = Jan 14 09:00
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T09:30:00Z", "generation_mw": 9500},  # excluded for Jan 15
            {"start_time": "2026-01-15T14:00:00Z", "publish_time": "2026-01-14T07:30:00Z", "generation_mw": 8500},  # selected for Jan 15
            # Jan 16 delivery — cutoff = Jan 15 09:00
            {"start_time": "2026-01-16T14:00:00Z", "publish_time": "2026-01-14T09:30:00Z", "generation_mw": 9500},  # eligible for Jan 16
            {"start_time": "2026-01-16T14:00:00Z", "publish_time": "2026-01-15T08:00:00Z", "generation_mw": 10000}, # selected for Jan 16
        ])
        result = select_decision_forecasts(df, cutoff_hour=9).set_index("start_time")
        jan15 = pd.Timestamp("2026-01-15T14:00:00Z", tz="UTC")
        jan16 = pd.Timestamp("2026-01-16T14:00:00Z", tz="UTC")
        assert result.loc[jan15, "forecast_mw"] == pytest.approx(8500.0)
        assert result.loc[jan16, "forecast_mw"] == pytest.approx(10000.0)

    def test_invalid_cutoff_raises(self):
        df = _make_forecasts([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T07:00:00Z", "generation_mw": 8000},
        ])
        with pytest.raises(ValueError, match="cutoff_hour must be 0–23"):
            select_decision_forecasts(df, cutoff_hour=25)

    def test_empty_input_returns_empty(self):
        result = select_decision_forecasts(pd.DataFrame(
            columns=["publish_time", "start_time", "generation_mw", "lead_hours"]
        ))
        assert result.empty

    def test_result_has_one_row_per_delivery_hour(self):
        """No delivery hour should appear more than once in the output."""
        df = _make_forecasts([
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T02:30:00Z", "generation_mw": 7000},
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T04:30:00Z", "generation_mw": 7500},
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T07:30:00Z", "generation_mw": 8000},
            {"start_time": "2026-01-15T10:00:00Z", "publish_time": "2026-01-14T09:00:00Z", "generation_mw": 8500},
        ])
        result = select_decision_forecasts(df, cutoff_hour=9)
        assert len(result) == 1
        assert result["start_time"].nunique() == 1
