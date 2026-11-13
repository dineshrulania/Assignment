import { useState } from 'react'
import {
  Activity, TrendingUp, TrendingDown, Target,
  BarChart3, Zap, Clock, AlertCircle,
} from 'lucide-react'
import Header from '@/components/layout/Header'
import KPICard from '@/components/ui/KPICard'
import CutoffSelector from '@/components/ui/CutoffSelector'
import AssumptionBanner from '@/components/ui/AssumptionBanner'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ErrorState from '@/components/ui/ErrorState'
import SectionHeader from '@/components/ui/SectionHeader'
import ForecastVsActualChart from '@/components/charts/ForecastVsActualChart'
import DailyMAEChart from '@/components/charts/DailyMAEChart'
import HorizonChart from '@/components/charts/HorizonChart'
import { useApi } from '@/hooks/useApi'
import { fetchDashboardSummary } from '@/api/client'
import { fmtMW, fmtPct, fmtSignedMW, fmtDateTimeFull, biasColour } from '@/lib/formatters'
import { useNavigate } from 'react-router-dom'

export default function OverviewPage() {
  const [cutoff, setCutoff] = useState(9)
  const navigate = useNavigate()

  const { data, loading, error, refetch } = useApi(
    () => fetchDashboardSummary({ start_date: '2026-01-01', end_date: '2026-01-31', cutoff_hour_utc: cutoff }),
    [cutoff],
  )

  const s = data?.summary
  const latestPublish = data?.timeseries?.slice(-1)[0]?.forecast_publish_time

  return (
    <div className="flex flex-col min-h-full">
      <Header title="Overview" subtitle="January 2026 · National GB Wind Generation" />

      <div className="flex-1 p-6 space-y-6 animate-fade-in">
        {/* Controls */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Day-Ahead Forecast Evaluation</h2>
            <p className="text-xs text-slate-600 mt-0.5">Elexon BMRS · FUELHH actuals vs WINDFOR forecasts</p>
          </div>
          <CutoffSelector value={cutoff} onChange={setCutoff} disabled={loading} />
        </div>

        {/* Assumption banner */}
        {data?.assumption_note && <AssumptionBanner note={data.assumption_note} />}

        {/* KPI row */}
        {loading ? (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <KPICard key={i} label="Loading…" value="" loading />)}
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={refetch} />
        ) : s ? (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard label="Mean Forecast" value={fmtMW(s.mean_forecast_mw, 0)}
              subvalue="Avg day-ahead forecast" icon={Zap} accent="cyan" />
            <KPICard label="Mean Actual" value={fmtMW(s.mean_actual_mw, 0)}
              subvalue="Avg metered output" icon={Activity} accent="emerald" />
            <KPICard label="MAE" value={fmtMW(s.mae_mw, 0)}
              subvalue="Mean absolute error" icon={Target} accent="amber"
              trendLabel={s.mae_mw < 500 ? '● Good accuracy' : s.mae_mw < 1500 ? '● Moderate' : '● High error'}
              trend={s.mae_mw < 500 ? 'down' : s.mae_mw < 1500 ? 'neutral' : 'up'} />
            <KPICard label="RMSE" value={fmtMW(s.rmse_mw, 0)}
              subvalue="Root mean square error" icon={BarChart3} accent="rose" />
            <KPICard label="Forecast Bias" value={
              <span className={biasColour(s.mbe_mw)}>{fmtSignedMW(s.mbe_mw)}</span>
            }
              subvalue={s.mbe_mw > 50 ? 'Overforecast tendency' : s.mbe_mw < -50 ? 'Underforecast tendency' : 'Near-neutral'}
              icon={s.mbe_mw > 0 ? TrendingUp : TrendingDown} accent={Math.abs(s.mbe_mw) > 200 ? 'rose' : 'blue'} />
            <KPICard label="Coverage" value={fmtPct(s.coverage_pct)}
              subvalue={`${s.n_matched_intervals}/${s.n_total_intervals} hours`}
              icon={Clock} accent={s.coverage_pct > 95 ? 'emerald' : 'amber'} />
          </div>
        ) : null}

        {/* Main chart */}
        <div className="card p-5">
          <SectionHeader
            title="Forecast vs Actual Generation"
            description="Day-ahead decision forecast compared to metered wind output · Jan 2026"
            action={
              latestPublish && (
                <div className="flex items-center gap-1.5 text-2xs text-slate-500">
                  <Clock size={11} />
                  <span>Last pub: {fmtDateTimeFull(latestPublish)}</span>
                </div>
              )
            }
          />
          <div className="mt-4">
            {loading ? <LoadingSpinner message="Loading timeseries…" fullHeight /> :
              error ? <ErrorState message={error} onRetry={refetch} /> :
              data?.timeseries?.length ? (
                <ForecastVsActualChart data={data.timeseries} showBrush height={300} />
              ) : null}
          </div>
        </div>

        {/* Bottom two-col */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Daily MAE */}
          <div className="card p-5">
            <SectionHeader title="Daily Forecast Error (MAE)"
              description="Click a bar to explore that day in detail" />
            <div className="mt-4">
              {loading ? <LoadingSpinner /> :
                error ? <ErrorState message={error} onRetry={refetch} /> :
                data?.daily?.length ? (
                  <DailyMAEChart data={data.daily}
                    onDayClick={(date) => navigate(`/forecast?date=${date}`)} />
                ) : null}
            </div>
          </div>

          {/* Horizon */}
          <div className="card p-5">
            <SectionHeader title="Accuracy by Forecast Lead Time"
              description="MAE and RMSE grouped by hours-ahead" />
            <div className="mt-4">
              {loading ? <LoadingSpinner /> :
                error ? <ErrorState message={error} onRetry={refetch} /> :
                data?.horizon?.length ? (
                  <HorizonChart data={data.horizon} />
                ) : null}
            </div>
          </div>
        </div>

        {/* Summary stats bar */}
        {s && (
          <div className="card p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center divide-x divide-border-subtle">
              <div>
                <p className="section-label mb-1">MAPE</p>
                <p className="mono text-lg font-semibold text-white">{s.mape_pct != null ? fmtPct(s.mape_pct) : '—'}</p>
              </div>
              <div>
                <p className="section-label mb-1">nMAE</p>
                <p className="mono text-lg font-semibold text-white">{fmtPct(s.nmae_pct)}</p>
              </div>
              <div>
                <p className="section-label mb-1">Avg Lead Time</p>
                <p className="mono text-lg font-semibold text-white">{s.mean_lead_hours.toFixed(1)}h</p>
              </div>
              <div>
                <p className="section-label mb-1">Matched Intervals</p>
                <p className="mono text-lg font-semibold text-white">{s.n_matched_intervals}/{s.n_total_intervals}</p>
              </div>
            </div>
          </div>
        )}

        {/* Methodology note */}
        <div className="flex gap-3 p-4 rounded-lg bg-navy-900 border border-border-subtle text-xs text-slate-500">
          <AlertCircle size={14} className="shrink-0 mt-0.5 text-slate-600" />
          <span>
            <strong className="text-slate-400">Assumption A2:</strong> Accuracy metrics are computed on hourly
            (HH:00) intervals only. WINDFOR forecasts are hourly; FUELHH actuals are half-hourly. The HH:30
            actuals are displayed in charts but excluded from MAE/RMSE/MBE calculations.
            Matched: {s?.n_matched_intervals ?? '—'} of 744 possible hourly intervals.
          </span>
        </div>
      </div>
    </div>
  )
}
