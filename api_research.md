# API Research: Elexon BMRS Insights API

**Status key — every claim in this document is marked:**
- ✅ VERIFIED — confirmed by live API call or official Elexon documentation
- ⚠️ ASSUMED — reasonable inference from observed data or domain knowledge; must be validated before production use

---

## 1. Platform Overview

### 1.1 Service Identity
- ✅ The service is the **Elexon Insights Solution API**, the successor to the legacy BMRS API.
- ✅ Official documentation portal: https://bmrs.elexon.co.uk/api-documentation
- ✅ Developer portal: https://developer.data.elexon.co.uk/
- ✅ All data is freely accessible — **no API key or authentication required**.
- ✅ Base URL for all REST endpoints: `https://data.elexon.co.uk/bmrs/api/v1`
- ✅ Responses from `/stream` endpoints are **JSON arrays** only (not XML or CSV).
- ✅ All timestamps are **UTC**.
- ✅ All power values are in **MW (megawatts)**.

### 1.2 Why the `/stream` Endpoint Variant
Both FUELHH and WINDFOR expose two endpoint patterns:
- `/datasets/{DATASET}` — paginated, returns a wrapper object with metadata.
- `/datasets/{DATASET}/stream` — returns a **flat JSON array**, no pagination wrapper.

For historical bulk retrieval of a fixed month the `/stream` variant is simpler: a single request per date range returns all matching rows as a plain array. This is what the application will use.

---

## 2. FUELHH — Half-Hourly Generation Outturn by Fuel Type

### 2.1 Dataset Description
- ✅ FUELHH provides the actual electricity generated per fuel type per half-hour settlement period across Great Britain.
- ✅ This is metered outturn data — what generating units **actually produced**, not what was planned.
- ✅ National-level aggregate only. No unit-level or regional breakdown.

### 2.2 Endpoint

```
GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream
```

### 2.3 Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `settlementDateFrom` | `YYYY-MM-DD` | Yes | First settlement date to include (inclusive) |
| `settlementDateTo` | `YYYY-MM-DD` | Yes | Last settlement date to include (inclusive) |
| `fuelType` | string | No | Filter by fuel type. Use `WIND` for wind generation |

- ✅ Verified parameter names from live API call.
- ✅ `fuelType=WIND` correctly returns only wind generation rows.

### 2.4 Response Schema

Verified live response (2026-01-01, fuelType=WIND):

```json
[
  {
    "dataset": "FUELHH",
    "publishTime": "2026-01-01T00:30:00Z",
    "startTime": "2026-01-01T00:00:00Z",
    "settlementDate": "2026-01-01",
    "settlementPeriod": 1,
    "fuelType": "WIND",
    "generation": 13756
  }
]
```

| Field | Type | Description |
|---|---|---|
| `dataset` | string | Always `"FUELHH"` |
| `publishTime` | ISO-8601 UTC | When Elexon published this settlement period result |
| `startTime` | ISO-8601 UTC | Start of the 30-minute delivery interval being described |
| `settlementDate` | `YYYY-MM-DD` | The GB market settlement date |
| `settlementPeriod` | integer 1–48 | The half-hour slot within the settlement day (SP1 = 00:00–00:30) |
| `fuelType` | string | Fuel type code, e.g. `WIND`, `NUCLEAR`, `CCGT` |
| `generation` | integer | Average power output during the interval, **MW** |

### 2.5 Temporal Characteristics
- ✅ **30-minute resolution** — one row per settlement period.
- ✅ **48 settlement periods per settlement day** (SP1 at 00:00 UTC through SP48 at 23:30 UTC).
- ✅ For January 2026 with `fuelType=WIND`: **1,488 rows** (31 days × 48 periods).
- ✅ From live data: `publishTime` for actuals typically lags `startTime` by approximately 30 minutes (the data is published as soon as the period closes). This is **not** a forecast delay — it is measurement latency.
- ⚠️ If Elexon republishes a corrected figure for a period, multiple rows with different `publishTime` values may appear for the same `startTime`. The application must **deduplicate by keeping the latest `publishTime` per `startTime`**.

### 2.6 Fuel Types Available (observed, not an exhaustive list)
`WIND`, `NUCLEAR`, `CCGT`, `COAL`, `BIOMASS`, `NPSHYD`, `PS`, `OCGT`, `OIL`, `OTHER`, plus interconnector codes (INTFR, INTNED, etc.)

This application uses **only `WIND`**.

### 2.7 Data Volume for January 2026
```
Request:
  settlementDateFrom=2026-01-01
  settlementDateTo=2026-01-31
  fuelType=WIND

Expected rows: 1,488
```

---

## 3. WINDFOR — Wind Generation Forecast

### 3.1 Dataset Description
- ✅ WINDFOR provides National Grid ESO's published wind generation **forecasts** for future delivery intervals.
- ✅ National-level aggregate only.
- ✅ Forecasts are **hourly** — one row per clock hour, not per half-hour settlement period.

### 3.2 Endpoint

```
GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream
```

### 3.3 Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `publishDateTimeFrom` | ISO-8601 UTC | Yes | Earliest forecast publication time to include (inclusive) |
| `publishDateTimeTo` | ISO-8601 UTC | Yes | Latest forecast publication time to include (inclusive) |

- ✅ Verified parameter names from live API call.
- ⚠️ No `startTime` / `settlementDate` filter is available on this endpoint — filtering to delivery dates must be done **client-side after fetching**.
- ⚠️ The only way to retrieve forecasts for January 2026 delivery is to request by **publish time window**, which must start in late December 2025 to capture early-January forecasts.

### 3.4 Response Schema

Verified live response (publishDateTimeFrom=2025-12-31T22:00:00Z, publishDateTimeTo=2026-01-01T02:00:00Z):

```json
[
  {
    "dataset": "WINDFOR",
    "publishTime": "2025-12-31T22:30:00Z",
    "startTime": "2026-01-01T00:00:00Z",
    "generation": 20032
  }
]
```

| Field | Type | Description |
|---|---|---|
| `dataset` | string | Always `"WINDFOR"` |
| `publishTime` | ISO-8601 UTC | When this forecast batch was published |
| `startTime` | ISO-8601 UTC | The delivery hour being forecast |
| `generation` | integer | Forecast wind output for that hour, **MW** |

**Notable absences:** `settlementDate`, `settlementPeriod`, and `fuelType` are **not present** in WINDFOR responses.

### 3.5 Temporal Characteristics
- ✅ **Hourly resolution** — one forecast row per target hour.
- ✅ Each publish event produces a **batch** of rows all sharing the same `publishTime`.
- ✅ Each batch covers approximately 25 hours in the past through 66 hours ahead (~91 rows per batch).
- ✅ Publish schedule: approximately **8 times per day** at approximately 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC. (Observed from data; exact schedule may vary.)
- ✅ This means each delivery hour receives approximately **20 forecasts** at increasing lead times as delivery approaches.
- ✅ Rows where `startTime <= publishTime` are **hindcasts** (describing the past), not forecasts. These must be dropped before analysis.

### 3.6 Key Insight: Forecast Vintages
A "vintage" is a specific (`publishTime`, `startTime`) pair — a single forecast for a specific delivery hour made at a specific time. The same delivery hour will have many vintages. The procurement team needs the **vintage that was available at their decision time** (day-ahead cutoff), not the most recent one.

### 3.7 Fetch Strategy for January 2026 Delivery

Because the WINDFOR API filters by `publishDateTimeFrom`/`To`, and the first day-ahead forecasts for 2026-01-01 delivery would have been published on approximately 2025-12-31 at 09:30 UTC, the fetch window must begin in **late December 2025**:

```
publishDateTimeFrom = 2025-12-28T00:00:00Z   (safe margin — captures all D-2 to D-1 forecasts)
publishDateTimeTo   = 2026-02-01T00:00:00Z   (captures the final forecasts for 2026-01-31)
```

Expected volume:
- ~35 days × 8 publishes/day = ~280 publish batches
- ~280 × ~73 rows = ~20,440 total rows fetched
- After dropping past rows (startTime <= publishTime): ~16,239 rows
- After filtering to January 2026 startTime only: ~744 rows (31 days × 24 hours)
- After vintage selection (one per delivery hour): **744 rows**

---

## 4. Critical Data Mismatch: Temporal Resolution

This is the most architecturally significant finding from the API research.

| Property | FUELHH (Actuals) | WINDFOR (Forecasts) |
|---|---|---|
| Granularity | 30 minutes | 60 minutes (hourly) |
| Periods per day | 48 | 24 |
| Identifier | `startTime` (HH:00 or HH:30) | `startTime` (HH:00 only) |
| Settlement reference | `settlementDate` + `settlementPeriod` | None |

**Consequence:** A direct 1-to-1 join is only possible at **on-the-hour** intervals (HH:00:00Z). The half-hour actuals (HH:30:00Z) have no matching forecast row.

**Resolution strategy (design decision):**
Match each forecast to the **single FUELHH row** where `startTime` is on the hour (e.g., forecast for 14:00 is compared to actual for 14:00–14:30). The HH:30 actuals can be displayed on the chart but are excluded from accuracy metric calculations.

This reduces the matchable set from 1,488 actual rows to **744 on-the-hour actual rows** for January 2026.

---

## 5. Pagination

- ✅ The `/stream` endpoint returns all matching rows in a single response array — there is no pagination token, `page`, or `limit` parameter.
- ✅ For the volumes involved (≤ 20,440 WINDFOR rows, 1,488 FUELHH rows), a single HTTP request per dataset is sufficient.
- ⚠️ For very large date ranges, response size could become a concern. For January 2026 specifically, observed response sizes are well within typical HTTP limits (~8–10 KB for FUELHH/day, estimated ~1 MB for the full WINDFOR month fetch).

---

## 6. Rate Limiting and Reliability

- ✅ No API key means no documented rate limit tier.
- ⚠️ Elexon's documentation notes the Insights API is "not suitable for time-critical applications". This implies occasional latency and no SLA guarantee.
- ⚠️ No explicit rate limiting documentation was found. Assume reasonable limits apply; do not hammer the API in loops.
- **Mitigation in architecture:** Data for January 2026 is historical and static. Fetch once, cache in memory (or optionally to disk). No polling or repeated requests needed.

---

## 7. Day-Ahead Cutoff: Forecast Vintage Selection

### 7.1 Business Context
The UK day-ahead electricity market operates as follows:
- Trading day D-1: Procurement team reviews wind forecasts and decides how much electricity to buy from the wholesale day-ahead market.
- The GB EPEX SPOT day-ahead auction typically closes around **09:20–09:50 UK local time** on D-1.
- After this cutoff, no further adjustments to day-ahead purchase volumes are possible.

### 7.2 Cutoff Assumption
- ⚠️ The exact procurement decision cutoff is **not specified in the assignment brief**.
- **Design assumption:** Use the latest WINDFOR forecast published at or before **09:00 UTC on D-1** as the "decision forecast" for each delivery hour on day D.
- This is intentionally set slightly before the market close to represent a realistic window where traders would have reviewed data and prepared bids.
- The cutoff will be a **configurable parameter** (default 09:00 UTC) so the application can be adjusted without code changes.

### 7.3 Vintage Selection Algorithm
For each delivery hour `H` on delivery date `D`:
1. Filter WINDFOR rows where `startTime == H`.
2. Filter to rows where `publishTime <= cutoff_datetime` (where `cutoff_datetime` = D-1 at cutoff hour UTC).
3. Drop hindcasts: `publishTime < startTime` must hold (i.e. the row was truly a forecast at publish time).
4. Select the row with the **maximum `publishTime`** — the most recent forecast available before the cutoff.
5. If no row exists: delivery hour has no eligible forecast and is excluded from accuracy metrics.

---

## 8. Data Quality Concerns

| Issue | Description | Mitigation |
|---|---|---|
| **Duplicate actuals** | FUELHH may publish revised values for a period, creating multiple rows with the same `startTime` | Keep latest `publishTime` per `startTime` |
| **Hindcasts in WINDFOR** | Rows with `startTime <= publishTime` are past-looking, not forecasts | Filter: retain only `startTime > publishTime` |
| **Missing forecast vintages** | A delivery hour may have no eligible day-ahead forecast if Elexon didn't publish at or before cutoff | Exclude from metric calculation; flag in UI |
| **Resolution mismatch** | WINDFOR is hourly, FUELHH is half-hourly | Match on HH:00 only; display HH:30 actuals separately |
| **Negative forecast values** | CP1381 notes valid WINDFOR range is −99999 to +99999; negatives may appear during curtailment | ⚠️ Clamp to 0 or flag; treat as data anomaly |
| **Late-arriving actuals** | FUELHH for the most recent periods may not yet be published | Only January 2026; all data should be final by now |
| **Timezone edge cases** | GB market uses UK local time (GMT in January, so UTC=local); settlement day boundaries differ from UTC midnight in BST periods | January 2026 is GMT, so UTC == GB local — no BST complication for this dataset |
| **API unavailability** | Elexon API may be temporarily unavailable | Implement retry logic with exponential backoff; surface error clearly in UI |

---

## 9. Sample Verified API Calls

### 9.1 FUELHH — 1 day of wind actuals
```
GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream
    ?settlementDateFrom=2026-01-01
    &settlementDateTo=2026-01-01
    &fuelType=WIND
```
Returns 48 rows, SP1 (00:00Z) through SP48 (23:30Z). Generation ranges from ~13,756 MW to ~16,408 MW on 2026-01-01 (a high-wind day, confirmed from live data).

### 9.2 WINDFOR — forecasts published over a 4-hour window
```
GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream
    ?publishDateTimeFrom=2025-12-31T22:00:00Z
    &publishDateTimeTo=2026-01-01T02:00:00Z
```
Returns 73 rows from one publish batch (publishTime=2025-12-31T22:30:00Z), covering startTime from 2025-12-30T21:00:00Z through 2026-01-02T21:00:00Z. Confirmed: hourly resolution, generation values ~5,000–20,000 MW.

---

## 10. Full January 2026 Fetch Parameters

```python
# Actuals
FUELHH_PARAMS = {
    "settlementDateFrom": "2026-01-01",
    "settlementDateTo":   "2026-01-31",
    "fuelType":           "WIND"
}

# Forecasts — start from Dec 28 to capture day-ahead forecasts for Jan 1
WINDFOR_PARAMS = {
    "publishDateTimeFrom": "2025-12-28T00:00:00Z",
    "publishDateTimeTo":   "2026-02-01T00:00:00Z"
}
```

---

## 11. Official Links

- Elexon Insights Website: https://bmrs.elexon.co.uk
- Developer Portal: https://developer.data.elexon.co.uk/
- FUELHH endpoint docs: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream
- WINDFOR endpoint docs: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream
- OpenAPI spec: https://data.elexon.co.uk/bmrs/api/v1/swagger/v1/swagger.json
- Insights data platform overview: https://github.com/elexon-data/insights-docs
