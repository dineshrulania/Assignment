# Software Architecture: Wind Generation Forecast Monitor

**Product:** UK electricity procurement wind forecast analytics platform
**Data scope:** National GB wind generation, January 2026
**Sources:** Elexon BMRS FUELHH (actuals) + WINDFOR (forecasts)

---

## 1. Architecture Overview

The application follows a **split frontend/backend architecture** with a clear separation of concerns:

- The **backend** owns all data fetching, cleaning, computation, and caching. It exposes a REST API.
- The **frontend** owns all visualisation, interaction, and presentation. It consumes the REST API.
- **No direct browser calls to Elexon** — all Elexon communication is proxied through the backend, which handles retries, caching, and error normalisation.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                              │
│                                                                     │
│   ┌───────────────────────────────────────────────────────────┐    │
│   │                React + Vite Frontend                      │    │
│   │                (Tailwind CSS, Recharts)                   │    │
│   │                                                           │    │
│   │  Dashboard Page     Day Detail Page    About/Methodology  │    │
│   └────────────────────────┬──────────────────────────────────┘    │
│                            │ HTTP/JSON (REST API)                   │
└────────────────────────────│────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Python FastAPI Backend                            │
│                   (Uvicorn, deployed on Render)                     │
│                                                                     │
│   ┌─────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│   │  API Routes │   │  Data Engine │   │   In-Memory Cache      │  │
│   │  /api/*     │──▶│  (Pandas +   │──▶│  raw_actuals_df        │  │
│   │             │   │   NumPy)     │   │  raw_forecasts_df      │  │
│   └─────────────┘   └──────┬───────┘   │  joined analysis cache │  │
│                            │           └────────────────────────┘  │
│                            │ httpx (async)                         │
└────────────────────────────│────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Elexon BMRS Insights API                          │
│              https://data.elexon.co.uk/bmrs/api/v1                 │
│                                                                     │
│   /datasets/FUELHH/stream          /datasets/WINDFOR/stream        │
│   (actual wind generation)         (wind generation forecasts)     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Version target | Rationale |
|---|---|---|---|
| Frontend framework | React | 18.x | Specified in brief |
| Frontend build | Vite | 5.x | Fast HMR; specified in brief |
| Styling | Tailwind CSS | 3.x | Utility-first; specified in brief |
| Charts | Recharts | 2.x | React-native; specified in brief |
| Backend framework | FastAPI | 0.111.x | Specified; async-native, auto OpenAPI docs |
| ASGI server | Uvicorn | 0.29.x | Standard FastAPI server |
| HTTP client | httpx | 0.27.x | Async HTTP; pairs naturally with FastAPI |
| Data processing | Pandas | 2.x | Specified in brief |
| Numerical | NumPy | 1.26.x | Specified; used for RMSE computation |
| Containerisation | Docker + Compose | — | Specified in brief |
| Frontend deployment | Vercel | — | Specified in brief |
| Backend deployment | Render | — | Specified in brief |

---

## 3. Project Directory Structure

```
wind-forecast-monitor/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app, CORS config, router registration
│   │   ├── config.py         # Settings (cutoff hour, date range, CORS origins)
│   │   ├── elexon.py         # Elexon API client (httpx, retry logic)
│   │   ├── processing.py     # Data cleaning, vintage selection, metrics
│   │   ├── cache.py          # In-memory cache module
│   │   ├── models.py         # Pydantic response schemas
│   │   └── routers/
│   │       ├── health.py     # GET /api/health
│   │       ├── analysis.py   # GET /api/analysis
│   │       └── chart.py      # GET /api/chart/day/{date}
│   ├── tests/
│   │   ├── test_processing.py
│   │   └── test_metrics.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── DayDetailPage.tsx
│   │   │   └── MethodologyPage.tsx
│   │   ├── components/
│   │   │   ├── SummaryMetricsPanel.tsx
│   │   │   ├── ForecastVsActualChart.tsx
│   │   │   ├── ErrorDistributionChart.tsx
│   │   │   ├── DailyMetricsTable.tsx
│   │   │   ├── HorizonAnalysisChart.tsx
│   │   │   ├── CutoffSelector.tsx
│   │   │   ├── StatusBanner.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   ├── api/
│   │   │   └── client.ts     # Typed API client, base URL from env
│   │   └── lib/
│   │       └── formatters.ts # MW formatting, date helpers
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── docker-compose.yml
├── vercel.json
├── render.yaml
└── README.md
```

---

## 4. Backend Architecture

### 4.1 Application Startup

On FastAPI startup (`@app.on_event("startup")`):
1. Fetch FUELHH data from Elexon for 2026-01-01 → 2026-01-31, fuelType=WIND.
2. Fetch WINDFOR data from Elexon for 2025-12-28T00:00:00Z → 2026-02-01T00:00:00Z.
3. Clean both datasets (dedup, drop hindcasts, type coercion).
4. Store raw cleaned DataFrames in module-level cache.
5. Log row counts and coverage.

This means the first API request after a cold start does not incur fetch latency. The UI benefits from instant response after startup.

### 4.2 Elexon Client (`elexon.py`)

```python
class ElexonClient:
    BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

    async def fetch_fuelhh(
        self,
        settlement_date_from: str,
        settlement_date_to: str,
        fuel_type: str = "WIND"
    ) -> list[dict]: ...

    async def fetch_windfor(
        self,
        publish_from: str,   # ISO-8601 UTC
        publish_to: str      # ISO-8601 UTC
    ) -> list[dict]: ...
```

- Uses `httpx.AsyncClient` with a 60-second timeout.
- Retry: up to 3 attempts with exponential backoff (1s, 2s, 4s) on 5xx or connection errors.
- Returns raw list of dicts; no processing at this layer.

### 4.3 Processing Engine (`processing.py`)

Five pure functions; no side effects; testable in isolation:

| Function | Input | Output |
|---|---|---|
| `clean_actuals(raw)` | List of FUELHH dicts | Cleaned actuals DataFrame |
| `clean_forecasts(raw)` | List of WINDFOR dicts | Cleaned forecasts DataFrame (hindcasts dropped) |
| `select_decision_forecasts(forecasts_df, cutoff_hour)` | Cleaned forecasts, int | Decision forecasts DataFrame (one row per delivery hour) |
| `join_and_compute_errors(actuals_df, decision_df)` | Two DataFrames | Joined analysis DataFrame with error columns |
| `compute_metrics(joined_df, period_label)` | Joined DataFrame | AccuracyMetrics object |

### 4.4 Cache Module (`cache.py`)

```python
# Module-level singletons — set once at startup
_raw_actuals_df: pd.DataFrame | None = None
_raw_forecasts_df: pd.DataFrame | None = None
_analysis_cache: dict[int, pd.DataFrame] = {}  # keyed by cutoff_hour

def get_analysis(cutoff_hour: int) -> pd.DataFrame:
    if cutoff_hour not in _analysis_cache:
        decision_df = select_decision_forecasts(_raw_forecasts_df, cutoff_hour)
        joined_df = join_and_compute_errors(_raw_actuals_df, decision_df)
        _analysis_cache[cutoff_hour] = joined_df
    return _analysis_cache[cutoff_hour]
```

### 4.5 Pydantic Models (`models.py`)

Pydantic v2 models for all API responses. These enforce types, provide automatic OpenAPI schema generation, and validate data before serialisation. Key models:

- `HealthResponse`
- `AnalysisParameters`
- `SummaryMetrics`
- `TimeseriesPoint`
- `DailyMetrics`
- `HorizonBucket`
- `AnalysisResponse` (composes the above)
- `DayDetailInterval`
- `DayDetailResponse`

---

## 5. Backend API Endpoints

### `GET /api/health`
Returns backend status and cache state.

```
Response 200:
{
  "status": "ok",
  "cache_loaded": true,
  "actuals_rows": 1488,
  "forecast_rows": 16239,
  "data_period": "2026-01-01 to 2026-01-31"
}
```

### `GET /api/analysis`
Main analysis endpoint. Returns full month metrics, timeseries, daily breakdown, and horizon analysis.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_date` | YYYY-MM-DD | 2026-01-01 | First delivery date |
| `end_date` | YYYY-MM-DD | 2026-01-31 | Last delivery date |
| `cutoff_hour_utc` | integer 0–23 | 9 | Day-ahead cutoff hour (UTC) |

```
Response 200: AnalysisResponse (see data_model.md §9.1)
Response 503: {"detail": "Data not yet loaded"}
Response 422: Pydantic validation error (bad parameters)
```

### `GET /api/chart/day/{date}`
Per-day detail: all 24 (or 48 for display) intervals with forecast vs actual.

**Path parameter:** `date` — YYYY-MM-DD, must be within 2026-01-01 to 2026-01-31.
**Query parameter:** `cutoff_hour_utc` — integer, default 9.

```
Response 200: DayDetailResponse (see data_model.md §9.2)
Response 404: {"detail": "Date not in analysis range"}
Response 503: {"detail": "Data not yet loaded"}
```

### `GET /api/forecasts/vintages`
Returns all forecast vintages for a specific delivery hour (for the "forecast evolution" chart).

**Query parameters:** `delivery_hour` (ISO-8601 UTC datetime), `limit` (default 50).

```
Response 200:
{
  "delivery_hour": "2026-01-15T14:00:00Z",
  "vintages": [
    {
      "publish_time": "2026-01-13T22:30:00Z",
      "generation_mw": 9200,
      "lead_hours": 39.5
    }
  ]
}
```

---

## 6. Frontend Architecture

### 6.1 Pages

#### Page 1: Dashboard (`/`)

The primary operational view. Answers: *"How accurate were day-ahead wind forecasts across January 2026?"*

**Sections:**
1. **Header / Controls bar**
   - Cutoff hour selector (dropdown: 07:00, 08:00, 09:00, 10:00, 11:00 UTC)
   - Data status indicator (loaded / loading / error)
   - Methodology disclaimer badge

2. **Summary Metrics Panel** — four KPI cards:
   - MAE (MW) with contextual colour coding
   - RMSE (MW)
   - Bias / MBE (MW) with direction indicator (▲ overforecast / ▼ underforecast)
   - Coverage % (matched intervals / total)

3. **Forecast vs Actual Timeseries Chart** (Recharts `ComposedChart`)
   - X axis: delivery datetime (Jan 1–31)
   - Y axis: generation (MW)
   - Lines: `forecast_mw` (blue) and `actual_mw` (green)
   - Shaded area: error band (forecast − actual)
   - Tooltip: shows both values + error on hover
   - Brush: zoom/pan the month

4. **Daily Error Bar Chart** (Recharts `BarChart`)
   - X axis: day of month
   - Y axis: daily MAE (MW)
   - Bars coloured by severity (green < 500 MW, amber 500–1500, red > 1500)
   - Click a bar → navigates to Day Detail page

5. **Forecast Horizon Chart** (Recharts `LineChart`)
   - X axis: forecast lead time bucket
   - Y axis: MAE (MW)
   - Shows degradation of accuracy at longer horizons

6. **Data Coverage Notice**
   - Shows number of matched vs total intervals
   - Flags any delivery hours with no eligible forecast

#### Page 2: Day Detail (`/day/:date`)

Answers: *"What happened on this specific delivery day?"*

**Sections:**
1. **Date navigation** (previous day / next day arrows, date picker)
2. **Day summary KPI cards** (MAE, MBE, RMSE for the day)
3. **Hourly Forecast vs Actual Chart**
   - 24 hourly points (forecast line + on-the-hour actual)
   - 48 half-hourly actual bars in background (lighter)
   - Tooltip: forecast publish time + lead hours
4. **Hourly Error Chart** (bar chart showing `error_mw` per hour)
   - Positive bars = overforecast (red), negative = underforecast (blue)
5. **Interval Data Table** — scrollable, all 24 hours:
   - Delivery hour | Forecast MW | Actual MW | Error MW | Forecast published at | Lead hours
6. **Back to Dashboard** link

#### Page 3: Methodology (`/methodology`)

Non-interactive documentation page. Answers: *"How does this tool work and what are its assumptions?"*

**Content:**
- Data sources (FUELHH + WINDFOR with links to Elexon)
- Explanation of publishTime vs startTime
- Day-ahead cutoff definition and assumption documentation
- Resolution mismatch explanation (why 744 not 1,488 intervals)
- Error metric definitions (MAE, RMSE, MBE)
- Error sign convention and business interpretation
- Full list of documented assumptions (from data_model.md §11)

### 6.2 State Management

No Redux or Zustand needed. React Query (`@tanstack/react-query`) handles:
- API call lifecycle (loading / error / success states)
- Response caching in the browser
- Refetch on cutoff hour change

The `cutoff_hour_utc` selection is stored in component state (lifted to `App.tsx`), passed as a query parameter to all API calls. Changing it triggers automatic refetch via React Query's `queryKey`.

### 6.3 Routing

React Router v6, three routes:

```tsx
<Routes>
  <Route path="/"           element={<DashboardPage />} />
  <Route path="/day/:date"  element={<DayDetailPage />} />
  <Route path="/methodology" element={<MethodologyPage />} />
</Routes>
```

### 6.4 API Client (`api/client.ts`)

```typescript
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchAnalysis(params: AnalysisParams): Promise<AnalysisResponse> { ... }
export async function fetchDayDetail(date: string, cutoffHour: number): Promise<DayDetailResponse> { ... }
export async function fetchHealth(): Promise<HealthResponse> { ... }
```

All types derived from the Pydantic response models (manually or via openapi-typescript code generation).

### 6.5 Environment Variables

| Variable | Scope | Value |
|---|---|---|
| `VITE_API_URL` | Frontend build-time | Backend URL (e.g. `https://my-backend.onrender.com`) |
| `CORS_ORIGINS` | Backend runtime | Comma-separated allowed origins (e.g. `https://my-app.vercel.app`) |

---

## 7. Deployment Architecture

### 7.1 Local Development (Docker Compose)

```yaml
# docker-compose.yml (simplified)
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - CORS_ORIGINS=http://localhost:5173

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on: [backend]
```

**Startup sequence:**
1. `docker compose up --build`
2. Backend starts, Uvicorn runs, startup event fetches Elexon data (~3–5 seconds).
3. Frontend dev server starts, proxies `/api/*` to backend.
4. Open `http://localhost:5173`.

### 7.2 Production Deployment

**Backend on Render:**
- Runtime: Docker (uses `backend/Dockerfile`)
- Port: 8000
- Environment variable: `CORS_ORIGINS=https://<vercel-app>.vercel.app`
- Free tier: Render spins down after inactivity → cold starts fetch Elexon data again (~5s delay on first request after spin-up). This is acceptable for this application.

**Frontend on Vercel:**
- Framework preset: Vite
- Root directory: `frontend/`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_URL=https://<render-service>.onrender.com`

**No shared domain / no CORS proxy needed** — CORS is handled by the FastAPI middleware using the `CORS_ORIGINS` env var.

### 7.3 Render Service Definition (`render.yaml`)

```yaml
services:
  - type: web
    name: wind-forecast-backend
    runtime: docker
    dockerfilePath: backend/Dockerfile
    envVars:
      - key: CORS_ORIGINS
        sync: false
```

### 7.4 Vercel Configuration (`vercel.json`)

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

---

## 8. Backend Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 9. CORS Configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware
import os

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

All API calls are GET-only. No auth, no POST, no mutation.

---

## 10. Error Handling Strategy

| Failure scenario | Backend behaviour | Frontend behaviour |
|---|---|---|
| Elexon API unreachable at startup | Log error, cache remains empty | Health check shows `cache_loaded: false`; StatusBanner shows "Data unavailable" |
| Elexon returns 5xx | Retry 3× with backoff; if all fail, raise HTTPException 503 | Error state shown; "Retry" button triggers re-fetch |
| Invalid query parameters | Pydantic validation → 422 response | Form validation prevents invalid values; show inline error |
| Date outside Jan 2026 | 404 from day detail endpoint | Date picker constrained to Jan 2026 range |
| Partial data (some hours missing) | Coverage % reported in response | Coverage notice shown; metrics footnoted with interval count |

---

## 11. Key Design Decisions and Rationale

| Decision | Alternative considered | Rationale |
|---|---|---|
| Fetch on startup, cache in memory | Fetch on each request | January 2026 is static historical data; re-fetching on every request would slow responses and risk Elexon rate limits |
| httpx for Elexon calls | requests (sync) | FastAPI is async; httpx.AsyncClient avoids blocking the event loop |
| Match WINDFOR to on-the-hour FUELHH only | Interpolate WINDFOR to 30-min | Interpolation would invent data; matching on existing resolution is honest |
| Cutoff as configurable parameter | Hard-code 09:00 | Traders may work on different deadlines; configurability surfaces the assumption |
| No database | SQLite / PostgreSQL | January 2026 is a small, static dataset; a DB adds complexity without benefit for this scope |
| No auth | JWT / session | Assignment scope is internal procurement tool; authentication is out of scope |
| React Query for state | Redux / Zustand | Query state (loading/error/cache) is exactly what React Query manages; no global app state needed |
