# Implementation Plan

**Product:** Wind Generation Forecast Monitor
**Budget:** 16 hours total development time
**Methodology:** Phased delivery — each phase produces working, demonstrable software.

---

## Guiding Principles

1. **Data first.** Prove the Elexon pipeline works before building any UI.
2. **Thin vertical slices.** Each phase delivers something end-to-end rather than completing one layer in isolation.
3. **Document assumptions in code.** Every assumption from `data_model.md` §11 must appear as a code comment at its point of use.
4. **No invented data.** If live Elexon data is unavailable during development, halt and debug — do not substitute mock values silently.
5. **Scope discipline.** Demand, solar, prices, and unit-level breakdowns are explicitly out of scope. Any feature that is not in this plan requires explicit scope agreement.

---

## Phase Overview

| Phase | Name | Hours | Cumulative |
|---|---|---|---|
| 1 | Project scaffold and dev environment | 1.5h | 1.5h |
| 2 | Elexon data pipeline (backend core) | 3.0h | 4.5h |
| 3 | FastAPI endpoints and response schemas | 2.0h | 6.5h |
| 4 | Frontend scaffold and API client | 1.5h | 8.0h |
| 5 | Dashboard page — charts and KPIs | 3.0h | 11.0h |
| 6 | Day detail page | 1.5h | 12.5h |
| 7 | Methodology page and UI polish | 1.0h | 13.5h |
| 8 | Docker, deployment, and verification | 1.5h | 15.0h |
| 9 | Final review, README, and submission prep | 1.0h | 16.0h |

---

## Phase 1 — Project Scaffold and Dev Environment (1.5h)

**Goal:** Both services start cleanly; developers can run the full stack locally.

### Tasks

1.1 Create top-level directory structure (`backend/`, `frontend/`, `docker-compose.yml`).

1.2 **Backend scaffold**
- `python -m venv .venv && pip install fastapi uvicorn httpx pandas numpy pydantic`
- Create `app/main.py` with a single `GET /api/health` returning `{"status": "ok"}`.
- Create `requirements.txt` with pinned versions.
- Verify: `uvicorn app.main:app --reload` runs without error.

1.3 **Frontend scaffold**
- `npm create vite@latest frontend -- --template react-ts`
- `npm install tailwindcss recharts react-router-dom @tanstack/react-query`
- `npx tailwindcss init -p`
- Replace default App.tsx with a skeleton that calls `GET /api/health` and shows the response.
- Verify: `npm run dev` runs; health call succeeds.

1.4 **Docker Compose**
- Write `backend/Dockerfile` and `frontend/Dockerfile`.
- Write `docker-compose.yml` wiring both services.
- Verify: `docker compose up --build` starts both; health check passes from browser.

1.5 Create `.env.example` files for both services. Add `.env` to `.gitignore`.

**Exit criteria:** `docker compose up --build` → browser at `http://localhost:5173` shows "Backend status: ok".

---

## Phase 2 — Elexon Data Pipeline (3.0h)

**Goal:** Raw data is fetched from Elexon, cleaned, and the joined analysis DataFrame is produced. All data quality rules from `data_model.md` are implemented and tested.

### Tasks

2.1 **Elexon client (`app/elexon.py`)**
- Implement `ElexonClient` with `fetch_fuelhh()` and `fetch_windfor()` using `httpx.AsyncClient`.
- Add retry logic: 3 attempts, exponential backoff on 5xx or connection error.
- Add structured logging: log URL, params, response row count, elapsed time.
- Manual smoke test: run a script that calls both endpoints and prints row counts.
  - Expected: FUELHH=1,488 rows, WINDFOR=~20,000 rows

2.2 **Actuals cleaning (`app/processing.py` — Part 1)**
- `clean_actuals(raw: list[dict]) -> pd.DataFrame`
- Filter `fuelType == "WIND"` (defensive).
- Parse `publishTime` and `startTime` as UTC datetimes.
- Deduplicate: keep latest `publishTime` per `startTime`.
- Sort ascending by `startTime`.
- Add `is_on_hour` boolean.
- Assert: 1,488 rows for January 2026; flag if different.
- Write unit test: given duplicate rows for same `startTime`, confirm dedup keeps latest.

2.3 **Forecasts cleaning (`app/processing.py` — Part 2)**
- `clean_forecasts(raw: list[dict]) -> pd.DataFrame`
- Parse datetimes as UTC.
- Drop hindcasts: keep only `start_time > publish_time`.
- Compute `lead_hours`.
- Clamp negative `generation_mw` to 0 (document assumption A6).
- Write unit test: given a mix of genuine forecasts and hindcasts, confirm hindcasts are dropped.

2.4 **Vintage selection (`app/processing.py` — Part 3)**
- `select_decision_forecasts(forecasts_df, cutoff_hour: int) -> pd.DataFrame`
- For each delivery hour, compute cutoff datetime = D-1 at cutoff_hour:00 UTC.
- Filter candidates: `start_time == H` and `publish_time <= cutoff_dt`.
- Select max `publish_time` per delivery hour.
- Document assumption A1 (cutoff = 09:00 UTC) as a comment.
- Write unit test: for a delivery hour at 14:00 on Jan 2, with three vintages at 06:00, 09:00, and 09:30 on Jan 1, confirm the 09:00 vintage is selected (not the 09:30, which is after cutoff).

2.5 **Join and error computation (`app/processing.py` — Part 4)**
- `join_and_compute_errors(actuals_df, decision_df) -> pd.DataFrame`
- Inner join on `start_time` (HH:00 only — document assumption A2).
- Compute `error_mw`, `abs_error_mw`, `sq_error_mw2`, `pct_error`.
- Write unit test: given known forecast/actual pairs, verify error columns are computed correctly.

2.6 **Metric computation (`app/processing.py` — Part 5)**
- `compute_metrics(joined_df, period_label) -> AccuracyMetrics`
- Compute MAE, RMSE, MBE, MAPE (with zero-actual guard), nMAE.
- Write unit tests for each metric formula using small synthetic DataFrames.
- Verify metrics match hand-calculated values.

2.7 **Startup cache loading (`app/cache.py` and `app/main.py`)**
- Implement module-level cache as described in `architecture.md §4.4`.
- Wire startup event: fetch → clean → cache.
- Log summary: "Cache loaded: 1488 actual rows, 16239 forecast rows".

**Exit criteria:** Running the backend logs correct row counts. All unit tests pass (`pytest`).

---

## Phase 3 — FastAPI Endpoints and Response Schemas (2.0h)

**Goal:** All three API endpoints return correct, validated JSON that matches the contracts in `data_model.md §9`.

### Tasks

3.1 **Pydantic models (`app/models.py`)**
- Define all response models listed in `architecture.md §4.5`.
- Use `model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})` to ensure clean UTC serialisation.

3.2 **`GET /api/health` (`app/routers/health.py`)**
- Return cache status, row counts, data period.
- Returns 503 if cache not loaded.

3.3 **`GET /api/analysis` (`app/routers/analysis.py`)**
- Accept `start_date`, `end_date`, `cutoff_hour_utc` query params with defaults.
- Validate date range is within 2026-01-01 → 2026-01-31.
- Call `cache.get_analysis(cutoff_hour)`.
- Filter joined_df to requested date range.
- Call `compute_metrics()`, build daily breakdown, build horizon breakdown.
- Return `AnalysisResponse`.
- Handle 503 if cache not loaded.

3.4 **`GET /api/chart/day/{date}` (`app/routers/chart.py`)**
- Validate date is within range; return 404 if not.
- Return both on-the-hour (forecast-matched) and half-hourly actuals for display.
- Include daily summary metrics.

3.5 **`GET /api/forecasts/vintages` (`app/routers/chart.py`)**
- Accept `delivery_hour` as ISO-8601 UTC string.
- Return all vintages for that delivery hour from the cleaned forecasts DataFrame.

3.6 **Integration test**
- Start the backend server.
- Call `GET /api/analysis` and verify response shape matches Pydantic schema.
- Call `GET /api/chart/day/2026-01-15` and verify 24 intervals returned.
- Confirm metrics are non-zero and plausible (MAE between 100 and 5,000 MW).

3.7 **CORS and OpenAPI**
- Configure CORS middleware.
- Verify `/docs` Swagger UI loads and all endpoints are documented.

**Exit criteria:** `curl "http://localhost:8000/api/analysis"` returns valid JSON with non-zero MAE. All endpoints return correct HTTP status codes for valid and invalid inputs.

---

## Phase 4 — Frontend Scaffold and API Client (1.5h)

**Goal:** React app routes work; typed API client fetches real backend data; loading and error states render correctly.

### Tasks

4.1 **React Router setup**
- Configure three routes: `/`, `/day/:date`, `/methodology`.
- Create skeleton page components for each.

4.2 **React Query setup**
- Wrap app in `QueryClientProvider`.
- Configure default retry (2 attempts) and staleTime (5 minutes).

4.3 **Typed API client (`src/api/client.ts`)**
- Implement `fetchAnalysis`, `fetchDayDetail`, `fetchHealth` using `fetch`.
- Use `import.meta.env.VITE_API_URL` as base URL.
- Export TypeScript interfaces matching the Pydantic response models.

4.4 **Shared layout components**
- Navigation bar with links to Dashboard, Methodology.
- `StatusBanner` component: shows "Data loading…", "Live data from Elexon BMRS", or error state.
- `LoadingSpinner` component.
- Global Tailwind base styles.

4.5 **CutoffSelector component**
- Dropdown with options: 07:00, 08:00, 09:00, 10:00, 11:00 UTC.
- State lifted to `App.tsx`, passed down as prop.
- Tooltip explaining the cutoff assumption.

4.6 **Verify wiring**
- Dashboard page calls `fetchAnalysis` with default params; logs raw response to console.
- Loading and error states render without crashing.

**Exit criteria:** Browser shows the navigation bar; console logs a valid analysis response; changing the cutoff selector triggers a new API call.

---

## Phase 5 — Dashboard Page — Charts and KPIs (3.0h)

**Goal:** The dashboard is fully functional — all four visualisations and the summary KPI panel render with real Elexon data.

### Tasks

5.1 **SummaryMetricsPanel component**
- Four KPI cards: MAE, RMSE, MBE (with sign indicator), Coverage %.
- Colour coding: MAE < 500 MW green, 500–1,500 MW amber, > 1,500 MW red.
- Format numbers with comma separators and "MW" suffix.
- Show matched interval count as a subtitle ("Based on 740/744 intervals").

5.2 **ForecastVsActualChart component** (Recharts `ComposedChart`)
- X axis: `start_time` formatted as "Jan 1" through "Jan 31".
- Y axis left: generation in MW (formatted as "15,000 MW").
- Lines: forecast (blue, solid) and actual (green, solid).
- Area between lines: shaded red where forecast > actual, blue where forecast < actual.
- Recharts `Brush` component for zoom/pan.
- Responsive container (100% width).
- Tooltip: show date, forecast MW, actual MW, error MW.

5.3 **DailyErrorBarChart component** (Recharts `BarChart`)
- X axis: day of month (1–31).
- Y axis: daily MAE (MW).
- Bar fill: colour-coded by severity.
- Click handler: `navigate('/day/2026-01-${day}')`.
- Reference line at monthly average MAE.

5.4 **HorizonAnalysisChart component** (Recharts `LineChart`)
- X axis: lead time bucket labels.
- Y axis: MAE (MW).
- Line for MAE, optional second line for RMSE.
- Annotation at the "day-ahead" range (24–36h) with an arrow.

5.5 **DailyMetricsTable component**
- Scrollable table, 31 rows.
- Columns: Date | Intervals | Mean Forecast | Mean Actual | MAE | MBE | RMSE.
- Row click navigates to Day Detail page.
- Sortable by MAE column.

5.6 **Page assembly**
- Compose all components in `DashboardPage.tsx`.
- Wire `cutoff_hour_utc` from app state to `fetchAnalysis`.
- Loading skeleton while data fetches.
- Error state with retry button.

5.7 **Methodology disclaimer**
- Persistent banner at top of page: "Forecasts shown are those available before 09:00 UTC on D-1. This is an analytical assumption, not a confirmed trading rule."
- Link to Methodology page.

**Exit criteria:** Dashboard renders all four charts with real Elexon data. Clicking a daily bar navigates to the correct day. Changing the cutoff refreshes all charts.

---

## Phase 6 — Day Detail Page (1.5h)

**Goal:** Drilling into any day shows the full 24-hour picture with forecast vs actual and interval-level error detail.

### Tasks

6.1 **Date navigation**
- Previous / next day buttons (`← 14 Jan` / `16 Jan →`).
- Constrain to January 2026 range.
- URL updates on navigation (`/day/2026-01-15`).

6.2 **Day summary KPI cards**
- MAE, MBE, RMSE for the selected day.
- Number of matched intervals.

6.3 **Hourly Forecast vs Actual Chart**
- 24 hourly points (forecast line + on-the-hour actual markers).
- 48 half-hourly actual bars in background (light grey, for context).
- Tooltip: delivery time, forecast MW, actual MW, error MW, forecast published at, lead hours.

6.4 **Hourly Error Chart**
- Bar chart: 24 bars showing `error_mw` per hour.
- Positive = overforecast (red), negative = underforecast (blue).
- Zero reference line.

6.5 **Interval Data Table**
- 24 rows (one per hour).
- Columns: Time | Forecast MW | Actual MW | Error MW | Published At | Lead Hours.
- Error column coloured by magnitude and sign.

6.6 **Back link and breadcrumb**

**Exit criteria:** Navigating to `/day/2026-01-15` shows 24 intervals of data. The hourly chart and error chart render correctly. Navigation between days works.

---

## Phase 7 — Methodology Page and UI Polish (1.0h)

**Goal:** The app is production-ready in appearance and all assumptions are documented in the UI.

### Tasks

7.1 **MethodologyPage content**
- Rendered from static JSX (no API call needed).
- Sections:
  - What this tool shows
  - Data sources (FUELHH + WINDFOR, with Elexon links)
  - Forecast publication time vs delivery time (with diagram)
  - Day-ahead cutoff definition and why it is an assumption
  - Resolution mismatch (hourly vs half-hourly) and matching approach
  - Error metric definitions
  - Error sign convention and business interpretation
  - Full assumption table (all 8 from `data_model.md §11`)

7.2 **UI polish**
- Consistent typography: heading sizes, font weights.
- Responsive layout: dashboard should be usable on 1280px+ desktop screens.
- Tailwind dark/light consistent colour palette throughout.
- Consistent chart colour palette across all charts.
- Number formatting: MW values with comma separators; decimals only where necessary.
- Empty/null states: "No data for this period" placeholder in charts.

7.3 **Favicon and page title**
- Set `<title>Wind Forecast Monitor</title>` in `index.html`.
- Add a simple wind/energy favicon (SVG, inline).

**Exit criteria:** Methodology page renders completely. No visual inconsistencies across pages. Responsive at 1280px.

---

## Phase 8 — Docker, Deployment, and Verification (1.5h)

**Goal:** The application runs identically in Docker locally and deploys cleanly to Vercel + Render.

### Tasks

8.1 **Backend Dockerfile hardening**
- Use `python:3.11-slim` base.
- Run as non-root user.
- Confirm `CORS_ORIGINS` env var is read correctly.
- Test: `docker build -t wind-backend ./backend` succeeds.

8.2 **Frontend production build**
- `npm run build` succeeds with zero warnings.
- Verify `dist/` output is correct.
- Test `VITE_API_URL` is embedded correctly in the build.

8.3 **Docker Compose end-to-end test**
- `docker compose up --build`.
- Navigate to `http://localhost:5173`, confirm dashboard loads with live data.
- Confirm `/api/health` returns `cache_loaded: true`.
- Confirm cutoff selector works end-to-end.

8.4 **Render backend deployment**
- Push code to GitHub.
- Create Render web service, set Docker runtime, set `CORS_ORIGINS`.
- Wait for deploy, verify `/api/health` returns 200.
- Test `/api/analysis` from curl.

8.5 **Vercel frontend deployment**
- Import GitHub repo to Vercel.
- Set `VITE_API_URL` to Render URL.
- Trigger deploy, verify app loads at Vercel URL.
- Test dashboard in incognito window (no browser cache).

8.6 **Cross-origin verification**
- Open deployed frontend, open browser network tab.
- Confirm `/api/analysis` call succeeds (no CORS error in console).

**Exit criteria:** Deployed app at Vercel URL loads, shows live Elexon data, cutoff selector works, day detail navigation works.

---

## Phase 9 — Final Review, README, and Submission Prep (1.0h)

**Goal:** Clean, documented, submission-ready repository.

### Tasks

9.1 **README.md**
- Project description and business purpose.
- Live links (Vercel frontend, Render backend, `/docs`).
- Local development setup (Option A: manual terminals; Option B: Docker Compose).
- Environment variable reference table.
- Architecture summary (3 sentences).
- Data source and assumption disclosures.
- AI assistance disclosure (if applicable).

9.2 **Final assumption audit**
- Read every entry in `data_model.md §11`.
- Confirm each assumption has a matching code comment at its point of enforcement.
- Confirm all assumption labels (A1–A8) appear in the Methodology page.

9.3 **Code review checklist**
- No hardcoded URLs or credentials.
- All API calls handle errors gracefully.
- No console.log statements left in production frontend code.
- Backend logs do not echo sensitive data.
- `requirements.txt` has pinned versions (no `>=`).

9.4 **Demo preparation**
- Plan a 10-minute walkthrough:
  - Part 1 (~5 min): customer-facing — open dashboard, explain KPIs, change cutoff, drill into a day, explain what it means for procurement.
  - Part 2 (~5 min): technical — architecture diagram, data pipeline, metric methodology, assumptions, deployment.

9.5 **Submission verification**
- Open deployed app in incognito window → confirms public access.
- Open GitHub repository → confirms public.
- Run `docker compose up --build` from a clean checkout → confirms reproducibility.

**Exit criteria:** README is complete. Repository is clean. Deployed app works in incognito. All assumption labels are traceable from `data_model.md` through code comments to the Methodology page.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Elexon API unavailable during development | Low | High | Implement retry logic early (Phase 2); use the verified live data to create a small fixture file for unit tests |
| WINDFOR data missing for early January | Low | Medium | Extend `publishDateTimeFrom` to 2025-12-24 as fallback |
| Render cold start too slow for demo | Medium | Low | Trigger a warm-up request before the demo; document expected cold-start time in README |
| Coverage < 100% (some hours missing forecast) | Low | Low | Report coverage % in UI; metrics are computed only over matched intervals |
| Recharts rendering performance with 744 points | Low | Low | Use `dot={false}` on line charts; Recharts handles this volume easily |
| Docker Compose port conflicts locally | Medium | Low | Document how to change ports in `.env` files |

---

## Explicitly Out of Scope

The following are **not** part of this implementation. Any request to add them must go through scope change:

- Demand-side data, solar generation, prices, or other fuel types
- Real-time or live data updates (the product is a January 2026 historical analysis)
- User authentication or login
- Database persistence (Postgres, SQLite, Redis)
- Unit-level (BM unit) or regional wind generation breakdown
- Comparison of multiple forecast providers
- Mobile-responsive layout (desktop ≥1280px is the target)
- Automatic data refresh or scheduled re-fetching
- CSV/Excel data export (may be added as a stretch feature if time permits)

---

## Dependencies Between Phases

```
Phase 1 (scaffold)
    └─► Phase 2 (data pipeline)
            └─► Phase 3 (API endpoints)
                    └─► Phase 4 (frontend scaffold + API client)
                                └─► Phase 5 (dashboard charts)
                                        ├─► Phase 6 (day detail)
                                        └─► Phase 7 (methodology + polish)
                                                    └─► Phase 8 (deployment)
                                                                └─► Phase 9 (final review)
```

Phases 5, 6, and 7 can partially overlap. Phase 8 (deployment) is independent of Phase 7 and can begin as soon as Phase 5 is stable.
