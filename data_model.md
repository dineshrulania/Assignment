# Data Model & Processing Methodology

**Status key:**
- ✅ VERIFIED — confirmed by live API data or domain fact
- ⚠️ ASSUMED — design decision or inference; documented explicitly

---

## 1. Raw Data Structures

These are the Python dataclass representations of the raw API payloads. They match exactly what the live API returns.

### 1.1 Raw FUELHH Record

```python
@dataclass
class RawActualRecord:
    dataset: str           # Always "FUELHH"  ✅
    publish_time: datetime # UTC — when Elexon published this result ✅
    start_time: datetime   # UTC — start of the 30-min delivery interval ✅
    settlement_date: date  # GB market date, e.g. 2026-01-15 ✅
    settlement_period: int # 1–48; SP1 = 00:00 UTC, SP48 = 23:30 UTC ✅
    fuel_type: str         # "WIND" after filtering ✅
    generation: float      # MW, average over the interval ✅
```

### 1.2 Raw WINDFOR Record

```python
@dataclass
class RawForecastRecord:
    dataset: str           # Always "WINDFOR" ✅
    publish_time: datetime # UTC — when this forecast batch was published ✅
    start_time: datetime   # UTC — the delivery HOUR being forecast ✅
    generation: float      # MW, forecast wind output for that hour ✅
    # Note: no settlement_date, settlement_period, or fuel_type fields ✅
```

---

## 2. Cleaned / Normalised Structures

After ingestion and cleaning, the data is held in Pandas DataFrames. All indices are UTC datetimes.

### 2.1 Actuals DataFrame

**Index:** `start_time` (UTC, 30-minute frequency)

| Column | Type | Description |
|---|---|---|
| `start_time` | datetime[UTC] | Period start, e.g. 2026-01-15T14:00:00Z |
| `settlement_date` | date | GB market date |
| `settlement_period` | int | 1–48 |
| `generation_mw` | float | Actual wind generation (MW) |
| `publish_time` | datetime[UTC] | Latest publish time (after dedup) |
| `is_on_hour` | bool | True when start_time minutes == 0 |

**Cleaning steps applied:**
1. Filter `fuelType == "WIND"` (defensive, already filtered at API level).
2. Deduplicate: for each `start_time`, keep the row with the **maximum `publish_time`** (handles Elexon revisions).
3. Sort ascending by `start_time`.
4. Validate: expect exactly 48 rows per settlement date; flag missing periods.
5. Add `is_on_hour` boolean column.

**Expected shape for January 2026:** 1,488 rows × 6 columns.

### 2.2 Forecasts DataFrame (all vintages)

**Index:** composite `(publish_time, start_time)`

| Column | Type | Description |
|---|---|---|
| `publish_time` | datetime[UTC] | When this forecast was published |
| `start_time` | datetime[UTC] | Delivery hour being forecast |
| `generation_mw` | float | Forecast wind output (MW) |
| `lead_hours` | float | Hours between publish and delivery (startTime − publishTime) |
| `is_genuine_forecast` | bool | True when start_time > publish_time |

**Cleaning steps applied:**
1. Drop hindcasts: retain only rows where `start_time > publish_time`.
2. Compute `lead_hours = (start_time - publish_time).total_seconds() / 3600`.
3. ⚠️ Clamp any negative `generation_mw` to 0 (defensive; CP1381 notes negatives are technically valid but represent data anomalies in this context).
4. Sort by `(start_time, publish_time)`.

**Expected shape for January 2026 delivery:** ~16,239 rows before delivery-date filtering.

---

## 3. The Forecast Vintage Selection Problem

This is the central analytical challenge of the application.

### 3.1 Terminology

| Term | Definition |
|---|---|
| **Delivery hour** | A specific UTC clock hour on a delivery date, e.g. 2026-01-15T14:00:00Z |
| **Forecast vintage** | A single (`publish_time`, `start_time`) pair — one forecast for one delivery hour made at one point in time |
| **Day-ahead cutoff** | The latest publication time the procurement team considers usable for a given delivery date |
| **Decision forecast** | The vintage selected for each delivery hour: the latest vintage published at or before the day-ahead cutoff |

### 3.2 Day-Ahead Cutoff Definition

```
cutoff_datetime(delivery_date D) = D-1 at <cutoff_hour>:00 UTC
```

- ⚠️ Default `cutoff_hour` = **09** (09:00 UTC).
- Rationale: The GB day-ahead electricity auction (EPEX SPOT) closes approximately 09:20–09:50 UK local time on D-1. January is GMT, so UK local = UTC. Setting the cutoff at 09:00 UTC ensures the selected forecast would have been available to a trader before submitting bids.
- The cutoff hour is a **configurable parameter** (0–23 UTC). It is not the official market rule; it is an operational proxy. This assumption must be disclosed clearly in the UI.

### 3.3 Vintage Selection Algorithm

```
Input:
  forecasts_df     — all WINDFOR rows for January 2026 delivery,
                     cleaned, hindcasts dropped
  delivery_hour H  — a specific UTC datetime (e.g. 2026-01-15T14:00:00Z)
  cutoff_hour      — integer 0-23 UTC (default 9)

Compute:
  delivery_date D  = date part of H
  cutoff_dt        = datetime(D.year, D.month, D.day - 1, cutoff_hour, 0, 0, tzinfo=UTC)

Filter:
  candidates       = forecasts_df[
                       (forecasts_df.start_time == H) &
                       (forecasts_df.publish_time <= cutoff_dt)
                     ]

Select:
  if len(candidates) == 0:
    return None     ← no eligible forecast; exclude from metrics

  decision_forecast = candidates.loc[candidates.publish_time.idxmax()]
  return decision_forecast
```

Applied across all 744 on-the-hour delivery hours in January 2026, this produces the **Decision Forecasts DataFrame**.

### 3.4 Decision Forecasts DataFrame

| Column | Type | Description |
|---|---|---|
| `start_time` | datetime[UTC] | Delivery hour (HH:00:00Z) |
| `forecast_mw` | float | Selected forecast wind output (MW) |
| `forecast_publish_time` | datetime[UTC] | When the selected forecast was published |
| `lead_hours` | float | Hours between publish and delivery |
| `cutoff_hour` | int | The cutoff hour used (parameter) |

**Expected shape:** up to 744 rows (31 days × 24 hours); fewer if any hours lack an eligible forecast.

---

## 4. Joined Analysis Dataset

The actuals and decision forecasts are joined on `start_time` (HH:00 only):

```
joined_df = decision_forecasts_df
              .merge(actuals_df[actuals_df.is_on_hour],
                     on="start_time",
                     how="inner")
```

| Column | Type | Description |
|---|---|---|
| `start_time` | datetime[UTC] | Delivery hour |
| `settlement_date` | date | GB market date |
| `settlement_period` | int | SP number (always odd: 1,3,5…47) |
| `forecast_mw` | float | Day-ahead forecast (MW) |
| `actual_mw` | float | Metered actual generation (MW) |
| `forecast_publish_time` | datetime[UTC] | When the decision forecast was published |
| `lead_hours` | float | Forecast lead time (hours) |
| `error_mw` | float | forecast_mw − actual_mw |
| `abs_error_mw` | float | \|forecast_mw − actual_mw\| |
| `sq_error_mw2` | float | (forecast_mw − actual_mw)² |
| `pct_error` | float | (forecast_mw − actual_mw) / actual_mw × 100 |

**Error sign convention:** `error = forecast − actual`
- Positive error → forecast overestimated wind → trader expected more wind generation → may have under-purchased electricity from the market → potential short position
- Negative error → forecast underestimated wind → may have over-purchased → potential long position

**Expected shape:** up to 744 rows; inner join excludes hours missing either actual or forecast.

---

## 5. Accuracy Metrics

All metrics are computed over the joined dataset for a given period (full month, single day, or subset).

### 5.1 Mean Absolute Error (MAE)

```
MAE = (1/N) × Σ |forecast_i − actual_i|
    = mean(abs_error_mw)
```

- **Interpretation:** Average magnitude of forecast error in MW. A MAE of 500 MW means the forecast was typically 500 MW off from actual.
- **Units:** MW
- **Preferred for:** operational communication (intuitive, same units as generation).

### 5.2 Root Mean Square Error (RMSE)

```
RMSE = √( (1/N) × Σ (forecast_i − actual_i)² )
     = √mean(sq_error_mw2)
```

- **Interpretation:** Penalises large errors more heavily than MAE. If RMSE >> MAE, the distribution has significant outliers (a few very bad hours).
- **Units:** MW
- **Preferred for:** identifying worst-case risk periods.

### 5.3 Mean Bias Error (MBE / Signed Bias)

```
MBE = (1/N) × Σ (forecast_i − actual_i)
    = mean(error_mw)
```

- **Interpretation:** Systematic directional bias. Positive MBE → forecast consistently overestimates wind → trader tends to hold short positions. Negative MBE → consistent underestimation.
- **Units:** MW
- **Business relevance:** Even a small systematic bias has significant financial consequences when compounded over many periods.

### 5.4 Mean Absolute Percentage Error (MAPE)

```
MAPE = (1/N) × Σ |error_i / actual_i| × 100
```

- **Units:** %
- ⚠️ **Limitation:** Undefined when `actual_i = 0` (zero wind periods). Division by zero must be handled; exclude zero-actual periods or use a modified MAPE.
- Use as a secondary metric alongside MAE/RMSE.

### 5.5 Normalised MAE (nMAE)

```
nMAE = MAE / mean(actual_mw) × 100
```

- **Units:** %
- Provides context: a 500 MW MAE is different if average generation is 1,000 MW vs 15,000 MW.

### 5.6 Summary Metrics Object

```python
@dataclass
class AccuracyMetrics:
    period_label: str         # e.g. "January 2026" or "2026-01-15"
    n_matched_intervals: int  # number of hours with both forecast and actual
    n_total_intervals: int    # 744 for full month
    coverage_pct: float       # n_matched / n_total * 100
    mae_mw: float
    rmse_mw: float
    mbe_mw: float             # signed bias
    mape_pct: float | None    # None if zero actuals present
    nmae_pct: float
    mean_actual_mw: float
    mean_forecast_mw: float
    mean_lead_hours: float
```

---

## 6. Daily Aggregation

For the daily breakdown view, metrics are computed per settlement date:

```python
daily_metrics = (
    joined_df
    .groupby("settlement_date")
    .agg(
        n_intervals    = ("start_time",    "count"),
        mean_forecast  = ("forecast_mw",   "mean"),
        mean_actual    = ("actual_mw",     "mean"),
        mae            = ("abs_error_mw",  "mean"),
        mbe            = ("error_mw",      "mean"),
        rmse           = ("sq_error_mw2",  lambda x: np.sqrt(x.mean())),
    )
    .reset_index()
)
```

---

## 7. Forecast Horizon Analysis

Groups metrics by lead time bucket to show how accuracy degrades as the forecast is made further in advance:

```python
horizon_buckets = {
    "12–18h":  (12, 18),
    "18–24h":  (18, 24),
    "24–30h":  (24, 30),
    "30–36h":  (30, 36),
    "36–48h":  (36, 48),
}
```

For day-ahead procurement the relevant lead time is typically **24–36 hours** ahead. Including shorter and longer horizons provides context on whether closer forecasts are indeed more accurate.

---

## 8. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    ELEXON BMRS API                          │
│                                                             │
│  FUELHH/stream                     WINDFOR/stream           │
│  settlementDateFrom=2026-01-01     publishDateTimeFrom=     │
│  settlementDateTo=2026-01-31         2025-12-28T00:00:00Z   │
│  fuelType=WIND                     publishDateTimeTo=        │
│  → 1,488 rows                        2026-02-01T00:00:00Z   │
│                                    → ~20,440 rows           │
└───────────────┬────────────────────────────┬────────────────┘
                │                            │
                ▼                            ▼
        ┌───────────────┐          ┌──────────────────┐
        │  Clean actuals│          │  Clean forecasts │
        │  Dedup by     │          │  Drop hindcasts  │
        │  latest pub   │          │  (startTime <=   │
        │  time         │          │   publishTime)   │
        │  1,488 rows   │          │  ~16,239 rows    │
        └───────┬───────┘          └────────┬─────────┘
                │                           │
                │                           ▼
                │                  ┌────────────────────┐
                │                  │  Select decision   │
                │                  │  forecast vintage  │
                │                  │  per delivery hour │
                │                  │  (cutoff D-1@09:00)│
                │                  │  → 744 rows        │
                │                  └────────┬───────────┘
                │                           │
                ▼                           ▼
        ┌──────────────────────────────────────────┐
        │            Inner join on start_time       │
        │       (on-the-hour actuals only)          │
        │            → up to 744 rows              │
        └───────────────────┬──────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────────┐
        │          Compute error columns           │
        │    error, abs_error, sq_error, pct_error │
        └───────────────────┬──────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │ Summary  │  │  Daily   │  │   Horizon    │
        │ metrics  │  │ metrics  │  │   analysis   │
        │ MAE/RMSE │  │ per day  │  │  by lead hrs │
        │ /MBE     │  │          │  │              │
        └──────────┘  └──────────┘  └──────────────┘
```

---

## 9. Frontend Data Contracts

These are the JSON shapes the FastAPI backend will return to the React frontend.

### 9.1 `GET /api/analysis` → AnalysisResponse

```json
{
  "parameters": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "cutoff_hour_utc": 9
  },
  "summary": {
    "n_matched_intervals": 740,
    "n_total_intervals": 744,
    "coverage_pct": 99.5,
    "mae_mw": 1250.4,
    "rmse_mw": 1687.2,
    "mbe_mw": 320.1,
    "mape_pct": 9.3,
    "nmae_pct": 8.1,
    "mean_actual_mw": 15430.0,
    "mean_forecast_mw": 15750.1,
    "mean_lead_hours": 27.3
  },
  "timeseries": [
    {
      "start_time": "2026-01-01T00:00:00Z",
      "settlement_date": "2026-01-01",
      "settlement_period": 1,
      "forecast_mw": 20032,
      "actual_mw": 13756,
      "forecast_publish_time": "2025-12-31T09:30:00Z",
      "lead_hours": 14.5,
      "error_mw": 6276,
      "abs_error_mw": 6276,
      "pct_error": 45.6
    }
  ],
  "daily": [
    {
      "settlement_date": "2026-01-01",
      "n_intervals": 24,
      "mean_forecast_mw": 18500.0,
      "mean_actual_mw": 15200.0,
      "mae_mw": 1800.0,
      "mbe_mw": 1200.0,
      "rmse_mw": 2100.0
    }
  ],
  "horizon": [
    {
      "bucket_label": "24–30h",
      "n_intervals": 150,
      "mae_mw": 1100.0,
      "mbe_mw": 280.0,
      "rmse_mw": 1450.0
    }
  ]
}
```

### 9.2 `GET /api/chart/day/{date}` → DayDetailResponse

```json
{
  "date": "2026-01-15",
  "intervals": [
    {
      "start_time": "2026-01-15T00:00:00Z",
      "settlement_period": 1,
      "forecast_mw": 8500,
      "actual_mw_on_hour": 8200,
      "actual_mw_half_hour": 8350,
      "error_mw": 300,
      "forecast_publish_time": "2026-01-14T09:30:00Z"
    }
  ],
  "daily_summary": {
    "mae_mw": 420.0,
    "mbe_mw": 180.0,
    "rmse_mw": 530.0
  }
}
```

Note: `actual_mw_half_hour` is the HH:30 actual for display purposes; it is excluded from metric calculations.

---

## 10. Caching Strategy

January 2026 is historical data — it will not change. The backend should:

1. On first request (or on startup): fetch both datasets from Elexon, clean, and store the joined DataFrame in an **in-memory cache** (Python dict / module-level variable).
2. On subsequent requests: serve from cache. No re-fetch.
3. The analysis endpoint is parametric on `cutoff_hour`. Since cutoff only affects vintage selection (not raw data), raw data is cached once and vintage selection is re-run per unique `cutoff_hour` value. ⚠️ Cache computed analyses per `(start_date, end_date, cutoff_hour)` key if performance requires it.
4. Expose a `GET /api/health` endpoint that reports cache status (loaded / not loaded, row counts).

---

## 11. Documented Assumptions

| # | Assumption | Rationale | Impact if wrong |
|---|---|---|---|
| A1 | Day-ahead cutoff = 09:00 UTC on D-1 | EPEX auction closes ~09:20–09:50 UK time (GMT in January) | Slight change to which vintage is selected; ~1–3 vintage rows affected per hour at most |
| A2 | Match on HH:00 actuals only | WINDFOR is hourly; no half-hour forecast exists | Halves the matchable point count; HH:30 errors are unquantifiable |
| A3 | Keep latest publish_time per FUELHH start_time | Handles Elexon revisions | Using an outdated value would corrupt actuals |
| A4 | Drop WINDFOR rows where start_time <= publish_time | These are hindcasts, not forecasts | Including them would artificially inflate available vintages |
| A5 | January 2026 is in GMT (UTC == GB local) | UK does not observe DST in January | No impact for this dataset; would matter for April–October data |
| A6 | Clamp negative generation_mw to 0 | CP1381 permits negatives; likely data artefact | Minor effect; actual negative generation is very rare for wind |
| A7 | "National" wind = FUELHH WIND aggregate | Assignment specifies national-level only; no BM unit breakdown | Correct per assignment scope |
| A8 | WINDFOR generation represents GB national wind | Assumption based on dataset description; National Grid ESO publishes this | Could include some offshore/embedded not in FUELHH; no way to verify from these two datasets alone |
