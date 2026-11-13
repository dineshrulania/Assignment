import { useState } from 'react'
import {
  Target, TrendingUp, TrendingDown,
  BarChart3, AlertCircle, ArrowUpRight, ArrowDownRight,
} from 'lucide-react'
import Header from '@/components/layout/Header'
import KPICard from '@/components/ui/KPICard'
import CutoffSelector from '@/components/ui/CutoffSelector'
import AssumptionBanner from '@/components/ui/AssumptionBanner'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ErrorState from '@/components/ui/ErrorState'
import SectionHeader from '@/components/ui/SectionHeader'
import StatusBadge from '@/components/ui/StatusBadge'
import ForecastVsActualChart from '@/components/charts/ForecastVsActualChart'
import ErrorDistributionChart from '@/components/charts/ErrorDistributionChart'
import DailyMAEChart from '@/components/charts/DailyMAEChart'
import HorizonChart from '@/components/charts/HorizonChart'
import ErrorTimeseriesChart from '@/components/charts/ErrorTimeseriesChart'
import { useApi } from '@/hooks/useApi'
import { fetchDashboardSummary, fetchErrors } from '@/api/client'
import {
  fmtMW, fmtPct, fmtSignedMW, biasColour, maeColour,
} from '@/lib/formatters'

export default function AccuracyPage() {
  const [cutoff, setCutoff] = useState(9)

  const { data, loading, error, refetch } = useApi(
    () => fetchDashboardSummary({
      start_date: '2026-01-01',
      end_date: '2026-01-31',
      cutoff_hour_utc: cutoff,
    }),
    [cutoff],
  )

  const { data: errData, loading: errLoading, error: errError } = useApi(
    () => fetchErrors({ start_date: '2026-01-01', end_date: '2026-01-31', cutoff_hour_utc: cutoff }),
    [cutoff],
  )

  const s = data?.summary

  /* ── Over/under split ── */
  const overPct = errData
    ? (errData.timeseries.filter(t => t.error_mw > 0).length / (errData.timeseries.length || 1)) * 100
    : null
  const underPct = overPct != null ? 100 - overPct : null

  return (
    <div className="flex flex-col min-h-full">
      <Header title="Accuracy Analysis" subtitle="Day-ahead forecast performance evaluation · January 2026" />

      <div className="flex-1 p-6 space-y-6 animate-fade-in">

        {/* Controls */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs text-slate-500">
              Measuring how well day-ahead wind forecasts predicted actual generation.
            </p>
          </div>
          <CutoffSelector value={cutoff} onChange={setCutoff} disabled={loading} />
        </div>

        {data?.assumption_note && <AssumptionBanner note={data.assumption_note} />}

        {/* KPI grid */}
        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <KPICard key={i} label="…" value="" loading />)}
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={refetch} />
        ) : s ? (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard
              label="MAE" value={<span className={maeColour(s.mae_mw)}>{fmtMW(s.mae_mw)}</span>}
              subvalue="Mean absolute error" icon={Target} accent="amber"
            />
            <KPICard
              label="RMSE" value={fmtMW(s.rmse_mw)}
              subvalue="Penalises outliers" icon={BarChart3} accent="rose"
            />
            <KPICard
              label="Bias (MBE)"
              value={<span className={biasColour(s.mbe_mw)}>{fmtSignedMW(s.mbe_mw)}</span>}
              subvalue={s.mbe_mw > 50 ? 'Systematic overforecast' : s.mbe_mw < -50 ? 'Systematic underforecast' : 'Near-neutral'}
              icon={s.mbe_mw >= 0 ? TrendingUp : TrendingDown}
              accent={Math.abs(s.mbe_mw) > 300 ? 'rose' : 'blue'}
            />
            <KPICard
              label="MAPE" value={s.mape_pct != null ? fmtPct(s.mape_pct) : 'N/A'}
              subvalue={s.mape_pct == null ? 'Zero-actual periods present' : 'Mean abs % error'}
              icon={Target} accent="amber"
            />
            <KPICard
              label="nMAE" value={fmtPct(s.nmae_pct)}
              subvalue="Normalised by mean actual" icon={Target} accent="blue"
            />
            <KPICard
              label="Coverage" value={fmtPct(s.coverage_pct)}
              subvalue={`${s.n_matched_intervals}/${s.n_total_intervals} intervals`}
              icon={Target} accent={s.coverage_pct > 95 ? 'emerald' : 'amber'}
            />
          </div>
        ) : null}

        {/* Over / under split */}
        {overPct != null && underPct != null && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card p-5 flex items-center gap-4">
              <div className="h-11 w-11 rounded-xl bg-rose-500/10 ring-1 ring-rose-500/20
                              flex items-center justify-center shrink-0">
                <ArrowUpRight size={20} className="text-rose-400" />
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-0.5">Overforecast hours</p>
                <p className="text-2xl font-semibold mono text-rose-400">{fmtPct(overPct)}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Forecast &gt; Actual — buyer could have been short on wind
                </p>
              </div>
            </div>
            <div className="card p-5 flex items-center gap-4">
              <div className="h-11 w-11 rounded-xl bg-cyan-500/10 ring-1 ring-cyan-500/20
                              flex items-center justify-center shrink-0">
                <ArrowDownRight size={20} className="text-cyan-400" />
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-0.5">Underforecast hours</p>
                <p className="text-2xl font-semibold mono text-cyan-400">{fmtPct(underPct)}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Forecast &lt; Actual — buyer may have over-purchased
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Forecast vs Actual chart */}
        <div className="card p-5">
          <SectionHeader
            title="Forecast vs Actual Generation"
            description="Day-ahead decision forecast vs metered wind output"
            action={s && (
              <StatusBadge
                variant={s.mbe_mw > 200 ? 'warning' : s.mbe_mw < -200 ? 'info' : 'ok'}
                label={s.mbe_mw > 50 ? 'Overforecast bias' : s.mbe_mw < -50 ? 'Underforecast bias' : 'Balanced'}
              />
            )}
          />
          <div className="mt-4">
            {loading ? <LoadingSpinner fullHeight /> :
              error ? <ErrorState message={error} onRetry={refetch} /> :
              data?.timeseries?.length ? (
                <ForecastVsActualChart data={data.timeseries} showBrush height={280} />
              ) : null}
          </div>
        </div>

        {/* Error timeseries + distribution */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="card p-5">
            <SectionHeader
              title="Forecast Error Over Time"
              description="error = forecast − actual · positive = overforecast"
            />
            <div className="mt-4">
              {errLoading ? <LoadingSpinner /> :
                errError ? <ErrorState message={errError} /> :
                errData?.timeseries.length ? (
                  <ErrorTimeseriesChart data={errData.timeseries} height={240} />
                ) : null}
            </div>
          </div>

          <div className="card p-5">
            <SectionHeader
              title="Error Distribution"
              description="Histogram of hourly forecast errors — symmetric = unbiased"
            />
            <div className="mt-4">
              {errLoading ? <LoadingSpinner /> :
                errError ? <ErrorState message={errError} /> :
                errData?.distribution.bins.length ? (
                  <ErrorDistributionChart
                    bins={errData.distribution.bins}
                    meanError={errData.distribution.mean_error_mw}
                    height={240}
                  />
                ) : null}
              {errData && (
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
                  <span>Mean error: <span className="mono text-slate-300">{fmtSignedMW(errData.distribution.mean_error_mw)}</span></span>
                  <span>Std dev: <span className="mono text-slate-300">{fmtMW(errData.distribution.std_error_mw)}</span></span>
                  <span>Intervals: <span className="mono text-slate-300">{errData.distribution.total_intervals}</span></span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Daily accuracy + horizon */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="card p-5">
            <SectionHeader title="Daily Forecast Error (MAE)" description="January 2026 day-by-day" />
            <div className="mt-4">
              {loading ? <LoadingSpinner /> :
                data?.daily?.length ? <DailyMAEChart data={data.daily} height={220} /> : null}
            </div>
          </div>
          <div className="card p-5">
            <SectionHeader
              title="Accuracy by Forecast Lead Time"
              description="Day-ahead window is 24–36h — does accuracy degrade further out?"
            />
            <div className="mt-4">
              {loading ? <LoadingSpinner /> :
                data?.horizon?.length ? <HorizonChart data={data.horizon} height={220} /> : null}
            </div>
          </div>
        </div>

        {/* Daily breakdown table */}
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b border-border-subtle">
            <SectionHeader title="Daily Accuracy Breakdown" description="All 31 days · January 2026" />
          </div>
          <div className="overflow-auto">
            {loading ? <LoadingSpinner /> :
              error ? <ErrorState message={error} onRetry={refetch} /> :
              data?.daily?.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th className="text-right">Mean Forecast</th>
                      <th className="text-right">Mean Actual</th>
                      <th className="text-right">MAE</th>
                      <th className="text-right">RMSE</th>
                      <th className="text-right">Bias</th>
                      <th className="text-right">Intervals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.daily.map(d => (
                      <tr key={d.settlement_date}>
                        <td className="mono text-slate-300 font-medium">{d.settlement_date}</td>
                        <td className="text-right mono text-cyan-300">{fmtMW(d.mean_forecast_mw)}</td>
                        <td className="text-right mono text-emerald-300">{fmtMW(d.mean_actual_mw)}</td>
                        <td className={`text-right mono font-medium ${maeColour(d.mae_mw)}`}>{fmtMW(d.mae_mw)}</td>
                        <td className="text-right mono text-rose-400">{fmtMW(d.rmse_mw)}</td>
                        <td className={`text-right mono ${biasColour(d.mbe_mw)}`}>{fmtSignedMW(d.mbe_mw)}</td>
                        <td className="text-right mono text-slate-500">{d.n_intervals}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
          </div>
        </div>

        {/* Methodology note */}
        <div className="flex gap-3 p-4 rounded-lg bg-navy-900 border border-border-subtle text-xs text-slate-500">
          <AlertCircle size={14} className="shrink-0 mt-0.5 text-slate-600" />
          <span>
            <strong className="text-slate-400">Error sign convention:</strong> error = forecast − actual.
            Positive = overforecast (wind was lower than predicted, buyer may have been short).
            Negative = underforecast (wind exceeded prediction, buyer may have over-purchased).
            Metrics computed on {s?.n_matched_intervals ?? '—'} matched hourly intervals (Assumption A2).
          </span>
        </div>
      </div>
    </div>
  )
}
