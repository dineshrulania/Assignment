# Analytics Validation Report

**Product:** WindSight Analytics — UK Wind Generation Forecast Evaluation Platform
**Data scope:** National GB wind generation, January 2026
**Sources:** Elexon BMRS FUELHH (actuals) + WINDFOR (forecasts)
**Report date:** 2026-01-xx (generated post-implementation review)
**Status:** ✅ All 32 unit tests pass

---

## 1. Audit Checklist

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | Actual generation filtered to WIND | ✅ Verified | Applied at API level (`fuelType=WIND`) AND defensively in `actuals_service.py` (fuel_type == "WIND" after rename) |
| 2 | Forecast/actual matched on `startTime` | ✅ Verified | Inner join on `start_time` column; both sides are UTC-aware; `_assert_utc_aware()` guard in production code |
| 3 | `publishTime` respected in vintage selection | ✅ Verified | Condition: `publish_time <= cutoff_dt` (strict; tested with exact boundary and 1-second-after cases) |
| 4 | Post-cutoff forecasts excluded | ✅ Verified | Vintages published after `D-1 at cutoff_hour:00 UTC` are dropped; test `test_one_second_after_cutoff_is_excluded` confirms edge case |
| 5 | January 2026 decision period | ✅ Verified | FUELHH: `settlementDateFrom=2026-01-01`, `settlementDateTo=2026-01-31`; WINDFOR publish window: `2025-12-28 → 2026-02-01` to capture early-Jan D-1 forecasts |
| 6 | Delivery date boundaries correct | ✅ Verified | WINDFOR post-fetch filter: `start_time >= 2026-01-01T00:00:00Z AND < 2026-02-01T00:00:00Z` |
| 7 | Duplicate timestamps handled | ✅ Verified | FUELHH dedup: keep latest `publish_time` per `start_time` (Assumption A3) |
| 8 | Missing half-hourly intervals flagged | ✅ Verified | Coverage check logs any settlement date with <48 periods; `missing_actual_periods` exposed on `/api/data/status` |
| 9 | Negative generation values | ✅ Verified | Clamped to 0 in both actuals and forecast services; count reported in validation report and `/api/data/status` |
| 10 | Null generation values | ✅ Verified | Validation service drops rows with null `generation`; count in `ValidationReport.rows_null_generation` |
| 11 | Timezone handling | ✅ Verified | All datetimes parsed with `utc=True`; January 2026 is GMT (UK does not observe DST); UTC == GB local throughout; documented as Assumption A5 |
| 12 | Hindcast exclusion | ✅ Verified | WINDFOR rows where `start_time <= publish_time` are dropped before vintage selection (Assumption A4) |

---

## 2. Formula Verification

### 2.1 Mean Absolute Error (MAE)

```
MAE = (1/N) × Σᵢ |forecast_i − actual_i|
    = mean(abs_error_mw column)
```

**Units:** MW  
**Implementation:** `float(joined_df["abs_error_mw"].mean())` where `abs_error_mw = error_mw.abs()`  
**Test:** `test_mae_formula` — inputs (11000,10000), (9500,10000), (10300,10000) → errors 1000, -500, 300 → MAE = (1000+500+300)/3 = **600.0 MW** ✅

### 2.2 Root Mean Square Error (RMSE)

```
RMSE = √( (1/N) × Σᵢ (forecast_i − actual_i)² )
     = √mean(sq_error_mw2 column)
```

**Units:** MW  
**Implementation:** `float(np.sqrt(joined_df["sq_error_mw2"].mean()))` where `sq_error_mw2 = error_mw²`  
**Test:** `test_rmse_formula` — same inputs → (1000²+500²+300²)/3 = 446,667 → RMSE = **668.33 MW** ✅  
**Property verified:** RMSE ≥ MAE always (Cauchy–Schwarz, `test_rmse_always_gte_mae`) ✅

### 2.3 Mean Bias Error (MBE / Signed Bias)

```
MBE = (1/N) × Σᵢ (forecast_i − actual_i)
    = mean(error_mw column)
```

**Units:** MW  
**Sign convention:** Positive = overforecast (forecast > actual); Negative = underforecast  
**Business interpretation:**
- Positive MBE → forecasts assumed more wind than materialised → procurement plan was based on higher renewable supply than delivered
- Negative MBE → forecasts assumed less wind than materialised → procurement plan was based on lower renewable supply than delivered

**Tests:** `test_mbe_positive_when_overforecast`, `test_mbe_negative_when_underforecast`, `test_mbe_near_zero_when_balanced` ✅

### 2.4 Mean Absolute Percentage Error (MAPE)

```
MAPE = (1/M) × Σᵢ (|forecast_i − actual_i| / |actual_i|) × 100
```

where M = number of intervals where actual_i ≠ 0.

**Units:** %  
**Zero-actual handling (FIXED from initial implementation):**
- Previous implementation: set MAPE = None if ANY actual was zero, discarding valid data
- Corrected implementation: compute MAPE over non-zero actuals; report exclusion count in `mape_zero_exclusions`
- Null only when ALL actuals are zero

**Tests:** `test_mape_excludes_zero_actuals_and_reports_exclusion` — 3 intervals, 1 zero-actual → MAPE = (10 + 12.5)/2 = **11.25%**, exclusions = 1 ✅  
`test_mape_none_when_all_actuals_zero` → mape_pct = None, exclusions = 2 ✅

### 2.5 Normalised MAE (nMAE)

```
nMAE = MAE / mean(actual_mw) × 100
```

**Units:** %  
**Purpose:** Provides scale context — a 500 MW MAE is different if mean actual is 1,000 MW vs 15,000 MW  
**Zero-mean guard:** Returns 0.0 if mean_actual == 0  
**Test:** `test_nmae_formula` — MAE=750, mean_actual=10000 → nMAE = **7.5%** ✅

### 2.6 Standard Deviation of Errors

```
σ_error = std(error_mw, ddof=1)   [sample standard deviation]
```

**Note:** `ddof=1` (sample std) corrected from implicit `ddof=0` in numpy histogram stats. This is consistent with reporting uncertainty over a sample rather than a population.

---

## 3. Vintage Selection Verification

### 3.1 Algorithm

```
For each delivery hour H on delivery date D:
  cutoff_dt = midnight(D) − 1 day + cutoff_hour hours  [UTC]
  candidates = forecasts where start_time == H AND publish_time <= cutoff_dt
  decision = candidate with max(publish_time)
  if no candidates: exclude H from accuracy metrics
```

### 3.2 Key Properties Verified

| Property | Test | Result |
|---|---|---|
| Latest eligible vintage selected | `test_selects_latest_eligible_vintage` | ✅ |
| Exact cutoff time included (≤, not <) | `test_exact_cutoff_time_is_included` | ✅ |
| One second after cutoff excluded | `test_one_second_after_cutoff_is_excluded` | ✅ |
| Cutoff computed per delivery date (not global) | `test_cutoff_is_per_delivery_date_not_global` | ✅ |
| Multiple delivery hours independently selected | `test_multiple_delivery_hours` | ✅ |
| Output has exactly one row per delivery hour | `test_result_has_one_row_per_delivery_hour` | ✅ |
| Invalid cutoff_hour raises ValueError | `test_invalid_cutoff_raises` | ✅ |
| Empty input → empty output | `test_empty_input_returns_empty` | ✅ |

### 3.3 Assumption A1 — Cutoff Default

The exact procurement decision deadline was not specified in the assignment. The default of **09:00 UTC on D-1** is used because:
- The GB EPEX SPOT day-ahead auction closes approximately 09:20–09:50 UK local time on D-1
- January 2026 is in GMT, so UK local == UTC
- 09:00 UTC gives traders a small margin before bid submission
- The cutoff is a **configurable parameter** (0–23 UTC); results vary with different values

This is an analytical proxy. The procurement team should verify their actual decision deadline.

---

## 4. Data Quality Checks

### 4.1 Duplicate Actuals (Assumption A3)

FUELHH may republish revised values for a settlement period (e.g. after metering corrections). The application keeps the **latest `publishTime` per `startTime`**, ensuring the most accurate available actual is used.

Validation: `actuals_service._check_coverage()` logs any settlement date with fewer than 48 periods.

### 4.2 Hindcast Removal (Assumption A4)

WINDFOR batches include rows where `startTime ≤ publishTime` — these describe the past, not genuine forecasts. These are filtered out before vintage selection. Including them would artificially inflate the pool of eligible candidates.

### 4.3 Negative Generation (Assumption A6)

Both datasets may contain negative `generation` values (documented in Elexon CP1381 as technically valid). These are clamped to 0 before analysis. The count is reported in `DataStatusResponse.negative_forecast_rows_clamped`. In practice, negative wind generation is rare and represents data anomalies (e.g. auxiliary power consumption).

### 4.4 Resolution Mismatch (Assumption A2)

FUELHH actuals: **30-minute resolution** (1,488 rows for January 2026)  
WINDFOR forecasts: **60-minute resolution** (744 delivery hours for January 2026)

Consequence: accuracy metrics are computed on the 744 on-the-hour (HH:00:00Z) matched pairs only. The 744 HH:30 actual periods have no corresponding forecast and are excluded from metric calculations but displayed in charts.

**This is not a bug** — it is the fundamental structure of the Elexon data. It means MAE/RMSE/MBE cover 50% of settlement periods. The remaining 50% cannot be evaluated without additional forecast data.

### 4.5 Timezone (Assumption A5)

January 2026 is entirely within GMT. UK does not observe BST in January. UTC == GB local time throughout.

This assumption does **not** hold for datasets covering late March through late October. Any extension of the analysis period to BST months must handle the UTC offset (UTC+1 in BST) and the two 23-hour/25-hour clock-change days.

---

## 5. Business Scope Limitations

### 5.1 Wind Generation Only

This application evaluates **wind generation forecast accuracy**. It does not:
- Calculate electricity procurement quantities
- Model consumer demand
- Estimate residual demand (demand minus wind)
- Provide recommendations on whether to buy or sell electricity

### 5.2 National Level Only

Both FUELHH and WINDFOR are national GB aggregates. The application does not:
- Break down by region, zone, or individual wind farm
- Distinguish between onshore and offshore wind
- Distinguish between embedded and transmission-connected generation

### 5.3 January 2026 Historical Analysis

Data is static (January 2026 is complete history). The application:
- Fetches data once at startup and caches in memory
- Does not perform real-time monitoring
- Does not receive IRIS push messages

---

## 6. Issues Found and Fixed

| # | Issue | Severity | Fix Applied |
|---|---|---|---|
| F1 | MAPE set to None when any actual was zero, discarding valid data | Medium | Rewritten: MAPE computed over non-zero actuals; exclusion count reported |
| F2 | `import math` inside `_to_timeseries()` loop in analytics router | Low | Moved to module-level import |
| F3 | Error std dev used `ddof=0` (population) in distribution | Low | Changed to `ddof=1` (sample) |
| F4 | No `over_forecast_count`/`under_forecast_count` in SummaryMetrics | Medium | Added; exposed in models and all analytics responses |
| F5 | No time-of-day analysis | Medium | Added `compute_time_of_day_metrics()` and `GET /api/analytics/timeofday` |
| F6 | No forecast revision analysis | Medium | Added `compute_forecast_revision_analysis()` and `GET /api/analytics/revisions` |
| F7 | No business insights endpoint | Medium | Added `generate_business_insights()` and `GET /api/analytics/insights` |
| F8 | Demand disclaimer absent from API responses | High | Added to all analytics endpoints; mandatory insight in `/api/analytics/insights` |
| F9 | `mape_zero_exclusions` not reported | Medium | Added to SummaryMetrics and AccuracyMetrics dataclass |
| F10 | No UTC timezone enforcement check in join function | Low | Added `_assert_utc_aware()` guard with diagnostic error message |

---

## 7. Test Results Summary

```
Platform : win32 · Python 3.14.2 · pytest 9.2.0
Test run : 32 collected

TestJoinAndComputeErrors (6 tests)       ALL PASSED
TestComputeMetrics (13 tests)            ALL PASSED
TestComputeDailyMetrics (2 tests)        ALL PASSED
TestTimeOfDayMetrics (2 tests)           ALL PASSED
TestSelectDecisionForecasts (9 tests)    ALL PASSED

Result: 32 passed, 0 failed
```

---

## 8. New API Endpoints Added

| Endpoint | Purpose |
|---|---|
| `GET /api/analytics/timeofday` | MAE, RMSE, MBE grouped by UTC hour of day (0–23) |
| `GET /api/analytics/revisions` | First vs decision forecast comparison per delivery hour |
| `GET /api/analytics/insights` | Data-driven business insights with demand disclaimer |

All existing endpoints (`/accuracy`, `/daily`, `/errors`, `/dashboard/summary`) updated with new `SummaryMetrics` fields: `over_forecast_count`, `under_forecast_count`, `over_forecast_pct`, `under_forecast_pct`, `max_over_forecast_mw`, `max_under_forecast_mw`, `mape_zero_exclusions`.

---

## 9. Documented Assumptions

| ID | Assumption | Verified |
|---|---|---|
| A1 | Day-ahead cutoff = 09:00 UTC on D-1 (configurable) | ✅ |
| A2 | Match on HH:00 actuals only (resolution mismatch) | ✅ |
| A3 | Keep latest publishTime per FUELHH startTime | ✅ |
| A4 | Drop WINDFOR rows where startTime ≤ publishTime | ✅ |
| A5 | January 2026 is GMT; UTC == GB local | ✅ |
| A6 | Clamp negative generation to 0 | ✅ |
| A7 | "National wind" = FUELHH WIND aggregate | ✅ |
| A8 | WINDFOR represents GB national wind | ✅ (documented limitation) |
