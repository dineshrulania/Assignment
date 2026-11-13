import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, RefreshCw, Clock, Wind } from 'lucide-react'
import Header from '@/components/layout/Header'
import CutoffSelector from '@/components/ui/CutoffSelector'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ErrorState from '@/components/ui/ErrorState'
import EmptyState from '@/components/ui/EmptyState'
import SectionHeader from '@/components/ui/SectionHeader'
import DayDetailChart from '@/components/charts/DayDetailChart'
import VintageChart from '@/components/charts/VintageChart'
import { useApi } from '@/hooks/useApi'
import { fetchDayDetail, fetchForecastVersions } from '@/api/client'
import { fmtMW, fmtSignedMW, fmtDateTimeFull } from '@/lib/formatters'
import type { DayDetailInterval } from '@/api/types'

const JAN_DATES = Array.from({ length: 31 }, (_, i) => {
  const d = i + 1
  return `2026-01-${String(d).padStart(2, '0')}`
})

export default function ForecastExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initDate = searchParams.get('date') ?? '2026-01-15'
  const [date, setDate] = useState(initDate)
  const [cutoff, setCutoff] = useState(9)
  const [selectedHour, setSelectedHour] = useState<string | null>(null)

  const dateIdx = JAN_DATES.indexOf(date)
  const prevDate = dateIdx > 0 ? JAN_DATES[dateIdx - 1] : null
  const nextDate = dateIdx < JAN_DATES.length - 1 ? JAN_DATES[dateIdx + 1] : null

  useEffect(() => {
    setSearchParams({ date }, { replace: true })
    setSelectedHour(null)
  }, [date, setSearchParams])

  const { data: dayData, loading, error, refetch } = useApi(
    () => fetchDayDetail(date, cutoff),
    [date, cutoff],
  )

  const selectedInterval = dayData?.intervals.find(i => i.hour_utc === selectedHour)
  const deliveryHour = selectedInterval
    ? `${date}T${selectedHour}:00Z`
    : null

  const { data: vintageData, loading: vintageLoading } = useApi(
    () => deliveryHour ? fetchForecastVersions(deliveryHour, 50) : Promise.resolve(null),
    [deliveryHour],
  )

  const s = dayData?.daily_summary

  return (
    <div className="flex flex-col min-h-full">
      <Header title="Forecast Explorer" subtitle={`${date} · Day-ahead wind generation forecasts`} />

      <div className="flex-1 p-6 space-y-6 animate-fade-in">
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4 justify-between">
          {/* Date navigator */}
          <div className="flex items-center gap-2">
            <button onClick={() => prevDate && setDate(prevDate)} disabled={!prevDate}
              className="btn-secondary p-2 disabled:opacity-30"><ChevronLeft size={15} /></button>
            <select value={date} onChange={e => setDate(e.target.value)}
              className="input-base text-sm mono min-w-[140px]">
              {JAN_DATES.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <button onClick={() => nextDate && setDate(nextDate)} disabled={!nextDate}
              className="btn-secondary p-2 disabled:opacity-30"><ChevronRight size={15} /></button>
          </div>
          <div className="flex items-center gap-3">
            <CutoffSelector value={cutoff} onChange={setCutoff} disabled={loading} />
            <button onClick={refetch} className="btn-ghost p-2"><RefreshCw size={14} /></button>
          </div>
        </div>

        {/* Day KPIs */}
        {s && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'MAE', value: fmtMW(s.mae_mw), colour: 'text-amber-400' },
              { label: 'RMSE', value: fmtMW(s.rmse_mw), colour: 'text-rose-400' },
              { label: 'Bias (MBE)', value: fmtSignedMW(s.mbe_mw), colour: s.mbe_mw > 0 ? 'text-rose-400' : 'text-cyan-400' },
              { label: 'Coverage', value: `${s.n_matched_intervals}/${s.n_total_intervals}`, colour: 'text-emerald-400' },
            ].map(k => (
              <div key={k.label} className="card p-4">
                <p className="section-label mb-1">{k.label}</p>
                <p className={`mono text-xl font-semibold ${k.colour}`}>{k.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Chart */}
        <div className="card p-5">
          <SectionHeader title="Hourly Generation — Forecast vs Actual"
            description="Click a bar to view forecast versions for that hour" />
          <div className="mt-4">
            {loading ? <LoadingSpinner fullHeight message="Loading day detail…" /> :
              error ? <ErrorState message={error} onRetry={refetch} /> :
              dayData?.intervals.length ? (
                <DayDetailChart data={dayData.intervals} height={300} />
              ) : <EmptyState />}
          </div>
        </div>

        {/* Table + vintage panel */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Interval table */}
          <div className="card p-0 overflow-hidden">
            <div className="p-4 border-b border-border-subtle">
              <SectionHeader title="Hourly Interval Detail"
                description="Select a row to view forecast vintages" />
            </div>
            <div className="overflow-auto max-h-[420px]">
              {loading ? <LoadingSpinner /> :
                error ? <ErrorState message={error} /> :
                !dayData?.intervals.length ? <EmptyState /> : (
                  <table className="data-table">
                    <thead className="sticky top-0 bg-navy-900 z-10">
                      <tr>
                        <th>Hour</th>
                        <th className="text-right">Forecast</th>
                        <th className="text-right">Actual</th>
                        <th className="text-right">Error</th>
                        <th className="text-right">Lead</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dayData.intervals.map((row: DayDetailInterval) => (
                        <tr key={row.hour_utc}
                          onClick={() => setSelectedHour(row.hour_utc === selectedHour ? null : row.hour_utc)}
                          className={`cursor-pointer ${row.hour_utc === selectedHour ? 'bg-accent-500/10 !border-accent-500/20' : ''}`}>
                          <td className="mono text-slate-300">{row.hour_utc}</td>
                          <td className="text-right mono text-cyan-300">
                            {row.forecast_mw != null ? fmtMW(row.forecast_mw) : <span className="text-slate-600">—</span>}
                          </td>
                          <td className="text-right mono text-emerald-300">
                            {row.actual_mw_on_hour != null ? fmtMW(row.actual_mw_on_hour) : <span className="text-slate-600">—</span>}
                          </td>
                          <td className="text-right mono">
                            {row.error_mw != null ? (
                              <span className={row.error_mw > 0 ? 'text-rose-400' : 'text-cyan-400'}>
                                {row.error_mw > 0 ? '+' : ''}{fmtMW(row.error_mw)}
                              </span>
                            ) : <span className="text-slate-600">—</span>}
                          </td>
                          <td className="text-right mono text-slate-500">
                            {row.lead_hours != null ? `${row.lead_hours.toFixed(1)}h` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </div>
          </div>

          {/* Vintage panel */}
          <div className="card p-5">
            {selectedHour ? (
              <>
                <SectionHeader
                  title={`Forecast Versions — ${selectedHour} UTC`}
                  description="All published forecasts for this delivery hour"
                />
                <div className="mt-4">
                  {vintageLoading ? <LoadingSpinner /> :
                    vintageData?.vintages.length ? (
                      <>
                        <VintageChart
                          data={vintageData.vintages}
                          actualMw={selectedInterval?.actual_mw_on_hour ?? undefined}
                          height={220}
                        />
                        <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                          <div className="bg-navy-800 rounded-lg p-3">
                            <p className="text-slate-500 mb-1">Vintages found</p>
                            <p className="mono text-white font-semibold text-base">{vintageData.n_vintages}</p>
                          </div>
                          <div className="bg-navy-800 rounded-lg p-3">
                            <p className="text-slate-500 mb-1">Decision forecast</p>
                            <p className="mono text-cyan-400 font-semibold text-base">
                              {selectedInterval?.forecast_mw != null ? fmtMW(selectedInterval.forecast_mw) : '—'}
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 overflow-auto max-h-[200px]">
                          <table className="data-table text-xs">
                            <thead className="sticky top-0 bg-navy-900">
                              <tr>
                                <th>Published</th>
                                <th className="text-right">Forecast</th>
                                <th className="text-right">Lead</th>
                              </tr>
                            </thead>
                            <tbody>
                              {vintageData.vintages.map((v, i) => (
                                <tr key={i}>
                                  <td className="mono text-slate-400 text-2xs">
                                    {fmtDateTimeFull(v.publish_time)}
                                  </td>
                                  <td className="text-right mono text-cyan-300">{fmtMW(v.generation_mw)}</td>
                                  <td className="text-right mono text-slate-500">{v.lead_hours.toFixed(1)}h</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    ) : (
                      <EmptyState title="No vintages" message="No forecast vintages found for this hour." />
                    )}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-3 text-center">
                <div className="h-12 w-12 rounded-full bg-navy-800 ring-1 ring-border flex items-center justify-center">
                  <Wind size={22} className="text-slate-500" />
                </div>
                <p className="text-sm text-slate-400">Select a row</p>
                <p className="text-xs text-slate-600 max-w-[200px]">
                  Click an interval in the table to view all forecast versions for that delivery hour.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Publication timestamps */}
        {dayData && !loading && (
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Clock size={13} className="text-slate-500" />
              <span className="text-xs font-medium text-slate-400">Forecast Publication Summary</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {dayData.intervals
                .filter(i => i.forecast_publish_time)
                .slice(0, 6)
                .map(i => (
                  <div key={i.hour_utc} className="flex items-center justify-between gap-3
                    text-xs bg-navy-800 rounded-lg px-3 py-2">
                    <span className="mono text-slate-400">{i.hour_utc} UTC</span>
                    <span className="text-slate-500 truncate">
                      {i.forecast_publish_time
                        ? fmtDateTimeFull(i.forecast_publish_time)
                        : '—'}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
