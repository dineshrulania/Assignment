// ─────────────────────────────────────────────────────────────────────────────
// API response types — mirrors the FastAPI Pydantic models exactly.
// All datetimes are ISO-8601 UTC strings (Z suffix).
// All power values are MW.
// ─────────────────────────────────────────────────────────────────────────────

// ── System ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded';
  cache_loaded: boolean;
  actuals_rows: number | null;
  forecast_rows: number | null;
  data_period: string | null;
  error: string | null;
}

export interface DataStatusResponse {
  cache_loaded: boolean;
  actuals_rows: number | null;
  forecast_rows: number | null;
  forecast_vintages: number | null;
  unique_delivery_hours: number | null;
  actuals_date_from: string | null;
  actuals_date_to: string | null;
  forecasts_publish_from: string | null;
  forecasts_publish_to: string | null;
  missing_actual_periods: number | null;
  negative_forecast_rows_clamped: number | null;
}

// ── Actuals ───────────────────────────────────────────────────────────────────

export interface ActualRecord {
  start_time: string;
  settlement_date: string;
  settlement_period: number;
  generation_mw: number;
  publish_time: string;
  is_on_hour: boolean;
}

export interface ActualsResponse {
  total_rows: number;
  on_hour_rows: number;
  records: ActualRecord[];
}

// ── Forecasts ─────────────────────────────────────────────────────────────────

export interface ForecastRecord {
  publish_time: string;
  start_time: string;
  generation_mw: number;
  lead_hours: number;
}

export interface ForecastsResponse {
  total_vintages: number;
  unique_delivery_hours: number;
  records: ForecastRecord[];
}

export interface ForecastVintagesResponse {
  delivery_hour: string;
  n_vintages: number;
  vintages: ForecastRecord[];
}

export interface LatestForecastRecord {
  start_time: string;
  generation_mw: number;
  publish_time: string;
  lead_hours: number;
}

export interface LatestForecastsResponse {
  cutoff_note: string;
  records: LatestForecastRecord[];
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface SummaryMetrics {
  period_label: string;
  n_matched_intervals: number;
  n_total_intervals: number;
  coverage_pct: number;
  mae_mw: number;
  rmse_mw: number;
  mbe_mw: number;
  mape_pct: number | null;
  mape_zero_exclusions: number;
  nmae_pct: number;
  mean_actual_mw: number;
  mean_forecast_mw: number;
  mean_lead_hours: number;
  over_forecast_count: number;
  under_forecast_count: number;
  over_forecast_pct: number;
  under_forecast_pct: number;
  max_over_forecast_mw: number;
  max_under_forecast_mw: number;
}

export interface TimeseriesPoint {
  start_time: string;
  settlement_date: string;
  settlement_period: number;
  forecast_mw: number;
  actual_mw: number;
  forecast_publish_time: string;
  lead_hours: number;
  error_mw: number;
  abs_error_mw: number;
  pct_error: number | null;
}

export interface DailyMetrics {
  settlement_date: string;
  n_intervals: number;
  mean_forecast_mw: number;
  mean_actual_mw: number;
  mae_mw: number;
  mbe_mw: number;
  rmse_mw: number;
}

export interface HorizonBucket {
  bucket_label: string;
  lead_hours_min: number;
  lead_hours_max: number;
  n_intervals: number;
  mae_mw: number;
  mbe_mw: number;
  rmse_mw: number;
}

export interface ErrorBin {
  bin_label: string;
  bin_min_mw: number;
  bin_max_mw: number;
  count: number;
  pct_of_total: number;
}

export interface ErrorDistributionResponse {
  cutoff_hour_utc: number;
  total_intervals: number;
  bins: ErrorBin[];
  mean_error_mw: number;
  std_error_mw: number;
}

export interface AnalysisParameters {
  start_date: string;
  end_date: string;
  cutoff_hour_utc: number;
}

export interface DashboardSummaryResponse {
  parameters: AnalysisParameters;
  summary: SummaryMetrics;
  timeseries: TimeseriesPoint[];
  daily: DailyMetrics[];
  horizon: HorizonBucket[];
  assumption_note: string;
}

export interface AccuracyResponse {
  parameters: AnalysisParameters;
  summary: SummaryMetrics;
  assumption_note: string;
}

export interface DailyAnalyticsResponse {
  parameters: AnalysisParameters;
  daily: DailyMetrics[];
}

export interface ErrorsResponse {
  parameters: AnalysisParameters;
  timeseries: TimeseriesPoint[];
  distribution: ErrorDistributionResponse;
}

// ── Day detail ────────────────────────────────────────────────────────────────

export interface DayDetailInterval {
  hour_utc: string;
  start_time: string;
  settlement_period_on_hour: number;
  forecast_mw: number | null;
  actual_mw_on_hour: number | null;
  actual_mw_half_hour: number | null;
  error_mw: number | null;
  forecast_publish_time: string | null;
  lead_hours: number | null;
}

export interface DayDetailResponse {
  date: string;
  intervals: DayDetailInterval[];
  daily_summary: SummaryMetrics | null;
  assumption_note: string;
}

// ── Shared query params ───────────────────────────────────────────────────────

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}

// ── Time-of-day analysis ──────────────────────────────────────────────────────

export interface TimeOfDayMetrics {
  hour_of_day: number;
  hour_label: string;
  n_intervals: number;
  mean_forecast_mw: number;
  mean_actual_mw: number;
  mae_mw: number;
  mbe_mw: number;
  rmse_mw: number;
}

export interface TimeOfDayResponse {
  parameters: AnalysisParameters;
  hours: TimeOfDayMetrics[];
  note: string;
}

// ── Forecast revision analysis ────────────────────────────────────────────────

export interface RevisionRecord {
  start_time: string;
  first_forecast_mw: number | null;
  first_publish_time: string | null;
  decision_forecast_mw: number;
  decision_publish_time: string;
  /** decision_forecast − first_forecast. Positive = revised upward. */
  revision_mw: number | null;
  actual_mw: number;
  decision_error_mw: number;
  first_error_mw: number | null;
}

export interface RevisionResponse {
  parameters: AnalysisParameters;
  records: RevisionRecord[];
  note: string;
}

// ── Business insights ─────────────────────────────────────────────────────────

export interface BusinessInsight {
  category: string;
  /** 'high' | 'medium' | 'low' | 'info' */
  severity: string;
  title: string;
  body: string;
  supporting_data: Record<string, unknown>;
}

export interface InsightsResponse {
  parameters: AnalysisParameters;
  n_insights: number;
  insights: BusinessInsight[];
  demand_disclaimer: string;
}
