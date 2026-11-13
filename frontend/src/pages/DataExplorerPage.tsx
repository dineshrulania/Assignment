import { useState, useMemo } from 'react'
import { Search, Download, Filter, Database, Wind, RefreshCw } from 'lucide-react'
import Header from '@/components/layout/Header'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ErrorState from '@/components/ui/ErrorState'
import EmptyState from '@/components/ui/EmptyState'
import SectionHeader from '@/components/ui/SectionHeader'
import Pagination from '@/components/ui/Pagination'
import StatusBadge from '@/components/ui/StatusBadge'
import { useApi } from '@/hooks/useApi'
import { fetchActuals, fetchForecasts, fetchDataStatus } from '@/api/client'
import { fmtMW, fmtDateTimeFull, fmtDate, exportCSV } from '@/lib/formatters'
import type { ActualRecord, ForecastRecord } from '@/api/types'

type Tab = 'actuals' | 'forecasts'

const PAGE_SIZE = 50

export default function DataExplorerPage() {
  const [tab, setTab] = useState<Tab>('actuals')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [dateFrom, setDateFrom] = useState('2026-01-01')
  const [dateTo, setDateTo] = useState('2026-01-31')
  const [onHourOnly, setOnHourOnly] = useState(false)

  /* ── Data fetching ── */
  const { data: status } = useApi(() => fetchDataStatus(), [])

  const { data: actualsData, loading: aLoading, error: aError, refetch: aRefetch } = useApi(
    () => fetchActuals({ start_date: dateFrom, end_date: dateTo, on_hour_only: onHourOnly }),
    [dateFrom, dateTo, onHourOnly],
  )

  const { data: forecastsData, loading: fLoading, error: fError, refetch: fRefetch } = useApi(
    () => fetchForecasts({ start_date: dateFrom, end_date: dateTo, limit: 5000 }),
    [dateFrom, dateTo],
  )

  /* ── Client-side search filter ── */
  const filteredActuals = useMemo<ActualRecord[]>(() => {
    if (!actualsData?.records) return []
    const q = search.toLowerCase()
    if (!q) return actualsData.records
    return actualsData.records.filter(r =>
      r.start_time.includes(q) ||
      r.settlement_date.includes(q) ||
      String(r.settlement_period).includes(q) ||
      String(r.generation_mw).includes(q),
    )
  }, [actualsData, search])

  const filteredForecasts = useMemo<ForecastRecord[]>(() => {
    if (!forecastsData?.records) return []
    const q = search.toLowerCase()
    if (!q) return forecastsData.records
    return forecastsData.records.filter(r =>
      r.start_time.includes(q) ||
      r.publish_time.includes(q) ||
      String(r.generation_mw).includes(q),
    )
  }, [forecastsData, search])

  /* ── Pagination ── */
  const rows = tab === 'actuals' ? filteredActuals : filteredForecasts
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const handleSearch = (v: string) => { setSearch(v); setPage(1) }
  const handleTab = (t: Tab) => { setTab(t); setPage(1); setSearch('') }

  /* ── CSV export ── */
  const handleExport = () => {
    if (tab === 'actuals' && filteredActuals.length) {
      exportCSV(
        filteredActuals.map(r => ({
          start_time: r.start_time,
          settlement_date: r.settlement_date,
          settlement_period: r.settlement_period,
          generation_mw: r.generation_mw,
          publish_time: r.publish_time,
          is_on_hour: r.is_on_hour,
        })),
        `windsight_actuals_${dateFrom}_${dateTo}.csv`,
      )
    } else if (tab === 'forecasts' && filteredForecasts.length) {
      exportCSV(
        filteredForecasts.map(r => ({
          start_time: r.start_time,
          publish_time: r.publish_time,
          generation_mw: r.generation_mw,
          lead_hours: r.lead_hours,
        })),
        `windsight_forecasts_${dateFrom}_${dateTo}.csv`,
      )
    }
  }

  const loading = tab === 'actuals' ? aLoading : fLoading
  const error   = tab === 'actuals' ? aError   : fError
  const refetch = tab === 'actuals' ? aRefetch  : fRefetch

  return (
    <div className="flex flex-col min-h-full">
      <Header title="Data Explorer" subtitle="Raw actuals and forecast records from Elexon BMRS" />

      <div className="flex-1 p-6 space-y-5 animate-fade-in">

        {/* Dataset status cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Actual Records', value: status?.actuals_rows?.toLocaleString() ?? '—', icon: Database, colour: 'text-emerald-400' },
            { label: 'Forecast Vintages', value: status?.forecast_vintages?.toLocaleString() ?? '—', icon: Wind, colour: 'text-cyan-400' },
            { label: 'Delivery Hours', value: status?.unique_delivery_hours?.toLocaleString() ?? '—', icon: Filter, colour: 'text-accent-400' },
            { label: 'Missing Periods', value: status?.missing_actual_periods?.toLocaleString() ?? '—', icon: Filter, colour: status?.missing_actual_periods ? 'text-amber-400' : 'text-emerald-400' },
          ].map(c => (
            <div key={c.label} className="card p-4 flex items-center gap-3">
              <div className={`h-9 w-9 rounded-lg bg-navy-800 ring-1 ring-border flex items-center justify-center shrink-0 ${c.colour}`}>
                <c.icon size={16} />
              </div>
              <div>
                <p className="text-2xs text-slate-500 uppercase tracking-wider">{c.label}</p>
                <p className={`mono text-lg font-semibold ${c.colour}`}>{c.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="card p-4">
          <div className="flex flex-wrap gap-3 items-end">
            {/* Tabs */}
            <div className="flex gap-1 p-1 bg-navy-800 rounded-lg">
              {(['actuals', 'forecasts'] as Tab[]).map(t => (
                <button key={t} onClick={() => handleTab(t)}
                  className={[
                    'px-4 py-1.5 rounded-md text-xs font-medium transition-all duration-150 capitalize',
                    tab === t ? 'bg-accent-500 text-white' : 'text-slate-400 hover:text-white',
                  ].join(' ')}>
                  {t}
                </button>
              ))}
            </div>

            {/* Date range */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500">From</label>
              <input type="date" value={dateFrom} min="2026-01-01" max="2026-01-31"
                onChange={e => { setDateFrom(e.target.value); setPage(1) }}
                className="input-base text-xs" />
              <label className="text-xs text-slate-500">To</label>
              <input type="date" value={dateTo} min="2026-01-01" max="2026-01-31"
                onChange={e => { setDateTo(e.target.value); setPage(1) }}
                className="input-base text-xs" />
            </div>

            {/* On-hour toggle (actuals only) */}
            {tab === 'actuals' && (
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <div className={`w-9 h-5 rounded-full transition-colors duration-200 relative
                  ${onHourOnly ? 'bg-accent-500' : 'bg-navy-700 ring-1 ring-border'}`}
                  onClick={() => { setOnHourOnly(!onHourOnly); setPage(1) }}>
                  <div className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform duration-200
                    ${onHourOnly ? 'translate-x-4' : 'translate-x-0.5'}`} />
                </div>
                <span className="text-xs text-slate-400">HH:00 only</span>
              </label>
            )}

            {/* Search */}
            <div className="flex-1 min-w-[180px] relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              <input
                value={search}
                onChange={e => handleSearch(e.target.value)}
                placeholder="Search date, time, MW…"
                className="input-base pl-8 w-full text-xs"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-2 ml-auto">
              <button onClick={refetch} className="btn-secondary flex items-center gap-2 text-xs">
                <RefreshCw size={13} /> Reload
              </button>
              <button onClick={handleExport} disabled={!rows.length}
                className="btn-primary flex items-center gap-2 text-xs">
                <Download size={13} /> Export CSV
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b border-border-subtle flex items-center justify-between gap-4">
            <SectionHeader
              title={tab === 'actuals' ? 'Actual Generation Records (FUELHH)' : 'Forecast Vintages (WINDFOR)'}
              description={
                tab === 'actuals'
                  ? 'Half-hourly metered wind generation · fuelType=WIND'
                  : 'All published forecast vintages for January 2026 delivery'
              }
            />
            <div className="flex items-center gap-2 shrink-0">
              <StatusBadge variant="ok" label={`${rows.length.toLocaleString()} rows`} />
            </div>
          </div>

          <div className="overflow-auto">
            {loading ? (
              <LoadingSpinner message="Loading records…" fullHeight />
            ) : error ? (
              <ErrorState message={error} onRetry={refetch} />
            ) : !pageRows.length ? (
              <EmptyState
                title="No records"
                message={search ? 'No records match your search.' : 'No data for this date range.'}
              />
            ) : tab === 'actuals' ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Start Time (UTC)</th>
                    <th>Settlement Date</th>
                    <th className="text-right">SP</th>
                    <th className="text-right">Generation</th>
                    <th>Published</th>
                    <th className="text-center">On Hour</th>
                  </tr>
                </thead>
                <tbody>
                  {(pageRows as ActualRecord[]).map((r, i) => (
                    <tr key={i}>
                      <td className="mono text-slate-200 text-xs">{r.start_time.replace('T', ' ').replace('Z', '')}</td>
                      <td className="mono text-slate-400 text-xs">{r.settlement_date}</td>
                      <td className="text-right mono text-slate-500 text-xs">{r.settlement_period}</td>
                      <td className="text-right mono text-emerald-300 font-medium">{fmtMW(r.generation_mw)}</td>
                      <td className="mono text-slate-500 text-xs">{r.publish_time.replace('T', ' ').replace('Z', '')}</td>
                      <td className="text-center">
                        <StatusBadge variant={r.is_on_hour ? 'ok' : 'neutral'}
                          label={r.is_on_hour ? 'Yes' : 'No'} dot={false} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Delivery Hour (UTC)</th>
                    <th>Published (UTC)</th>
                    <th className="text-right">Forecast</th>
                    <th className="text-right">Lead Time</th>
                  </tr>
                </thead>
                <tbody>
                  {(pageRows as ForecastRecord[]).map((r, i) => (
                    <tr key={i}>
                      <td className="mono text-slate-200 text-xs">{r.start_time.replace('T', ' ').replace('Z', '')}</td>
                      <td className="mono text-slate-400 text-xs">{r.publish_time.replace('T', ' ').replace('Z', '')}</td>
                      <td className="text-right mono text-cyan-300 font-medium">{fmtMW(r.generation_mw)}</td>
                      <td className="text-right mono text-slate-500">{r.lead_hours.toFixed(1)}h</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          {!loading && !error && rows.length > PAGE_SIZE && (
            <div className="p-4 border-t border-border-subtle">
              <Pagination
                page={page}
                totalPages={totalPages}
                onPage={setPage}
                pageSize={PAGE_SIZE}
                totalRows={rows.length}
              />
            </div>
          )}
        </div>

        {/* Source info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-500">
          <div className="card p-4 space-y-2">
            <p className="font-semibold text-slate-400">Actuals (FUELHH)</p>
            <p>Source: <code className="mono text-slate-400">GET /datasets/FUELHH/stream</code></p>
            <p>Filter: <code className="mono text-slate-400">fuelType=WIND</code></p>
            <p>Range: <code className="mono text-slate-400">2026-01-01 → 2026-01-31</code></p>
            <p>Expected: <code className="mono text-slate-400">1,488 rows (31 × 48 SPs)</code></p>
          </div>
          <div className="card p-4 space-y-2">
            <p className="font-semibold text-slate-400">Forecasts (WINDFOR)</p>
            <p>Source: <code className="mono text-slate-400">GET /datasets/WINDFOR/stream</code></p>
            <p>Filter: publish window <code className="mono text-slate-400">2025-12-28 → 2026-02-01</code></p>
            <p>Hindcasts removed: <code className="mono text-slate-400">startTime ≤ publishTime</code></p>
            <p>Retained: <code className="mono text-slate-400">~16,239 genuine forecast rows</code></p>
          </div>
        </div>
      </div>
    </div>
  )
}
