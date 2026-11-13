/**
 * Centralised API service.
 *
 * All requests go through this module. The base URL is read from
 * VITE_API_URL at build time; in development the Vite proxy handles
 * /api/* automatically so the env var is optional.
 *
 * Error contract:
 *   - Network/5xx errors throw ApiError with a human-readable message.
 *   - 422 validation errors throw ApiError with the detail string.
 *   - 404 throws ApiError so callers can distinguish "not found".
 *   - Callers must never receive raw Axios errors.
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import type {
  AccuracyResponse,
  ActualsResponse,
  DailyAnalyticsResponse,
  DashboardSummaryResponse,
  DataStatusResponse,
  DayDetailResponse,
  ErrorsResponse,
  ForecastVintagesResponse,
  ForecastsResponse,
  HealthResponse,
  InsightsResponse,
  LatestForecastsResponse,
  RevisionResponse,
  TimeOfDayResponse,
} from './types';

// ─────────────────────────────────────────────────────────────────────────────
// Error class
// ─────────────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Axios instance
// ─────────────────────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { Accept: 'application/json' },
});

// Normalise all errors into ApiError
http.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response) {
      const data = err.response.data as Record<string, unknown>;
      const detail =
        typeof data?.detail === 'string'
          ? data.detail
          : JSON.stringify(data?.detail ?? data ?? '');
      throw new ApiError(
        `API error ${err.response.status}: ${detail}`,
        err.response.status,
        detail,
      );
    }
    if (err.request) {
      throw new ApiError(
        'No response from server. Check your connection or backend status.',
      );
    }
    throw new ApiError(err.message ?? 'Unknown request error');
  },
);

// ─────────────────────────────────────────────────────────────────────────────
// Helper
// ─────────────────────────────────────────────────────────────────────────────

function buildParams(obj: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(obj)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, String(v)]),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// API surface
// ─────────────────────────────────────────────────────────────────────────────

// ── System ────────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/api/health');
  return data;
}

export async function fetchDataStatus(): Promise<DataStatusResponse> {
  const { data } = await http.get<DataStatusResponse>('/api/data/status');
  return data;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export async function fetchDashboardSummary(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<DashboardSummaryResponse> {
  const { data } = await http.get<DashboardSummaryResponse>(
    '/api/dashboard/summary',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

// ── Actuals ───────────────────────────────────────────────────────────────────

export async function fetchActuals(params?: {
  start_date?: string;
  end_date?: string;
  on_hour_only?: boolean;
}): Promise<ActualsResponse> {
  const { data } = await http.get<ActualsResponse>('/api/actuals', {
    params: buildParams(params ?? {}),
  });
  return data;
}

// ── Forecasts ─────────────────────────────────────────────────────────────────

export async function fetchForecasts(params?: {
  start_date?: string;
  end_date?: string;
  limit?: number;
}): Promise<ForecastsResponse> {
  const { data } = await http.get<ForecastsResponse>('/api/forecasts', {
    params: buildParams(params ?? {}),
  });
  return data;
}

export async function fetchLatestForecasts(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<LatestForecastsResponse> {
  const { data } = await http.get<LatestForecastsResponse>(
    '/api/forecasts/latest',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

export async function fetchForecastVersions(
  deliveryHour: string,
  limit = 50,
): Promise<ForecastVintagesResponse> {
  const { data } = await http.get<ForecastVintagesResponse>(
    '/api/forecasts/versions',
    { params: { delivery_hour: deliveryHour, limit } },
  );
  return data;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export async function fetchAccuracy(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<AccuracyResponse> {
  const { data } = await http.get<AccuracyResponse>('/api/analytics/accuracy', {
    params: buildParams(params ?? {}),
  });
  return data;
}

export async function fetchDailyAnalytics(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<DailyAnalyticsResponse> {
  const { data } = await http.get<DailyAnalyticsResponse>(
    '/api/analytics/daily',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

export async function fetchErrors(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<ErrorsResponse> {
  const { data } = await http.get<ErrorsResponse>('/api/analytics/errors', {
    params: buildParams(params ?? {}),
  });
  return data;
}

export async function fetchTimeOfDay(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<TimeOfDayResponse> {
  const { data } = await http.get<TimeOfDayResponse>(
    '/api/analytics/timeofday',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

export async function fetchRevisions(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<RevisionResponse> {
  const { data } = await http.get<RevisionResponse>(
    '/api/analytics/revisions',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

export async function fetchInsights(params?: {
  start_date?: string;
  end_date?: string;
  cutoff_hour_utc?: number;
}): Promise<InsightsResponse> {
  const { data } = await http.get<InsightsResponse>(
    '/api/analytics/insights',
    { params: buildParams(params ?? {}) },
  );
  return data;
}

// ── Chart / day detail ────────────────────────────────────────────────────────

export async function fetchDayDetail(
  date: string,
  cutoffHour = 9,
): Promise<DayDetailResponse> {
  const { data } = await http.get<DayDetailResponse>(`/api/chart/day/${date}`, {
    params: { cutoff_hour_utc: cutoffHour },
  });
  return data;
}
