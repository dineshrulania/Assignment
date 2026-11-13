import { useState } from 'react'
import {
  Settings, Database, Info, ExternalLink,
  CheckCircle, AlertTriangle, Loader2,
} from 'lucide-react'
import Header from '@/components/layout/Header'
import { useApi } from '@/hooks/useApi'
import { fetchHealth, fetchDataStatus } from '@/api/client'
import { fmtDateTimeFull } from '@/lib/formatters'

export default function SettingsPage() {
  const [cutoffDefault, setCutoffDefault] = useState(9)
  const [saved, setSaved] = useState(false)

  const { data: health, loading: hLoading, refetch: hRefetch } = useApi(() => fetchHealth(), [])
  const { data: status, loading: sLoading, refetch: sRefetch } = useApi(() => fetchDataStatus(), [])

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  return (
    <div className="flex flex-col min-h-full">
      <Header title="Settings" subtitle="Application configuration and data source information" />

      <div className="flex-1 p-6 space-y-6 animate-fade-in max-w-3xl">

        {/* Backend connection */}
        <section className="card p-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-accent-500/10 ring-1 ring-accent-500/20
                            flex items-center justify-center">
              <Database size={16} className="text-accent-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Backend Connection</h2>
              <p className="text-xs text-slate-500 mt-0.5">FastAPI service status and cache state</p>
            </div>
            <button onClick={() => { hRefetch(); sRefetch() }}
              className="ml-auto btn-secondary text-xs flex items-center gap-1.5">
              {hLoading || sLoading ? <Loader2 size={12} className="animate-spin" /> : null}
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'API Status', value: health?.status ?? '—',
                ok: health?.status === 'ok' },
              { label: 'Cache Loaded', value: health?.cache_loaded ? 'Yes' : 'No',
                ok: health?.cache_loaded === true },
              { label: 'Actual Records', value: health?.actuals_rows?.toLocaleString() ?? '—',
                ok: (health?.actuals_rows ?? 0) > 0 },
              { label: 'Forecast Vintages', value: health?.forecast_rows?.toLocaleString() ?? '—',
                ok: (health?.forecast_rows ?? 0) > 0 },
            ].map(item => (
              <div key={item.label} className="bg-navy-800 rounded-lg px-4 py-3 flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500">{item.label}</span>
                <div className="flex items-center gap-2">
                  <span className="mono text-sm font-medium text-white">{item.value}</span>
                  {item.ok
                    ? <CheckCircle size={13} className="text-emerald-400" />
                    : <AlertTriangle size={13} className="text-amber-400" />}
                </div>
              </div>
            ))}
          </div>

          {health?.error && (
            <div className="flex gap-2 p-3 rounded-lg bg-rose-500/8 border border-rose-500/20 text-xs text-rose-300">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>{health.error}</span>
            </div>
          )}

          <div className="text-xs text-slate-600 space-y-1">
            <p>Data period: <span className="text-slate-400">{health?.data_period ?? '—'}</span></p>
            <p>Backend URL: <span className="mono text-slate-400">{import.meta.env.VITE_API_URL || 'http://localhost:8000 (proxy)'}</span></p>
          </div>
        </section>

        {/* Data quality */}
        {status && (
          <section className="card p-5 space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-emerald-500/10 ring-1 ring-emerald-500/20
                              flex items-center justify-center">
                <CheckCircle size={16} className="text-emerald-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Data Quality Report</h2>
                <p className="text-xs text-slate-500 mt-0.5">Cache state at last load</p>
              </div>
            </div>

            <div className="space-y-2 text-xs">
              {[
                { label: 'Actuals fetch window', value: `${status.actuals_date_from} → ${status.actuals_date_to}` },
                { label: 'Forecasts publish window', value: `${status.forecasts_publish_from} → ${status.forecasts_publish_to}` },
                { label: 'Missing actual periods', value: status.missing_actual_periods === 0 ? '0 — full coverage ✓' : `${status.missing_actual_periods} periods missing` },
                { label: 'Negative forecasts clamped', value: status.negative_forecast_rows_clamped === 0 ? '0 — none found' : `${status.negative_forecast_rows_clamped} rows clamped to 0` },
                { label: 'Unique delivery hours', value: status.unique_delivery_hours?.toLocaleString() ?? '—' },
              ].map(row => (
                <div key={row.label} className="flex justify-between gap-4 py-2 border-b border-border-subtle/50 last:border-0">
                  <span className="text-slate-500">{row.label}</span>
                  <span className="mono text-slate-300">{row.value}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Analysis defaults */}
        <section className="card p-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-amber-500/10 ring-1 ring-amber-500/20
                            flex items-center justify-center">
              <Settings size={16} className="text-amber-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Analysis Defaults</h2>
              <p className="text-xs text-slate-500 mt-0.5">Default parameters used when no value is specified</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Default Day-Ahead Cutoff Hour (UTC)
              </label>
              <div className="flex items-center gap-3">
                <select value={cutoffDefault} onChange={e => setCutoffDefault(Number(e.target.value))}
                  className="input-base text-sm mono w-32">
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{String(i).padStart(2, '0')}:00 UTC</option>
                  ))}
                </select>
                <span className="text-xs text-slate-500">
                  {cutoffDefault === 9 ? '← Recommended (EPEX auction ≈ 09:20–09:50 UK time)' : ''}
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1.5">
                This sets which WINDFOR vintage is used as the "decision forecast" per delivery hour.
              </p>
            </div>

            <button onClick={handleSave}
              className={`btn-primary flex items-center gap-2 text-sm transition-all ${saved ? 'bg-emerald-500 hover:bg-emerald-500' : ''}`}>
              {saved ? <CheckCircle size={14} /> : <Settings size={14} />}
              {saved ? 'Saved!' : 'Save Defaults'}
            </button>
          </div>
        </section>

        {/* Documented assumptions */}
        <section className="card p-5 space-y-3">
          <div className="flex items-center gap-3 mb-1">
            <div className="h-9 w-9 rounded-lg bg-blue-500/10 ring-1 ring-blue-500/20
                            flex items-center justify-center">
              <Info size={16} className="text-accent-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Documented Assumptions</h2>
              <p className="text-xs text-slate-500 mt-0.5">From data_model.md §11</p>
            </div>
          </div>

          {[
            { id: 'A1', title: 'Day-ahead cutoff = 09:00 UTC on D-1',
              body: 'The GB EPEX SPOT auction closes ~09:20–09:50 UK local time (GMT in January = UTC). 09:00 UTC gives traders a margin before bid submission. This is an analytical proxy, not a confirmed client rule.' },
            { id: 'A2', title: 'Match on HH:00 actuals only',
              body: 'WINDFOR forecasts are hourly; FUELHH actuals are half-hourly. Accuracy metrics cover 744 on-the-hour intervals, not 1,488. HH:30 actuals are displayed but excluded from MAE/RMSE/MBE.' },
            { id: 'A3', title: 'Keep latest publishTime per FUELHH startTime',
              body: 'Elexon may republish revised settlement values. We always keep the most recently published value per settlement period.' },
            { id: 'A4', title: 'Drop WINDFOR rows where startTime ≤ publishTime',
              body: 'Such rows are hindcasts (describing the past), not genuine forecasts. Including them would artificially inflate the pool of available vintage candidates.' },
            { id: 'A5', title: 'January 2026 is in GMT (UTC == GB local)',
              body: 'The UK does not observe DST in January. Settlement day boundaries align with UTC midnight. This assumption would not hold for data in BST periods (late March – late October).' },
            { id: 'A6', title: 'Clamp negative generation_mw to 0',
              body: 'CP1381 permits negative WINDFOR values technically, but they represent data anomalies in this context. Negative actuals are very rare for wind.' },
            { id: 'A7', title: '"National" wind = FUELHH WIND aggregate',
              body: 'The assignment specifies national-level only. No BM unit or regional breakdown is used.' },
            { id: 'A8', title: 'WINDFOR represents GB national wind',
              body: 'Based on dataset description; National Grid ESO publishes this. It could include some offshore/embedded generation not in FUELHH — unverifiable from these two datasets alone.' },
          ].map(a => (
            <div key={a.id} className="flex gap-3 p-3 rounded-lg bg-navy-800 border border-border-subtle">
              <span className="shrink-0 h-5 w-8 rounded text-2xs font-bold mono bg-accent-500/20
                               text-accent-400 flex items-center justify-center">{a.id}</span>
              <div>
                <p className="text-xs font-medium text-slate-300">{a.title}</p>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{a.body}</p>
              </div>
            </div>
          ))}
        </section>

        {/* External links */}
        <section className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Data Sources & References</h2>
          {[
            { label: 'Elexon BMRS Insights Website', url: 'https://bmrs.elexon.co.uk' },
            { label: 'FUELHH Stream Endpoint Docs', url: 'https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream' },
            { label: 'WINDFOR Stream Endpoint Docs', url: 'https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream' },
            { label: 'Elexon Developer Portal', url: 'https://developer.data.elexon.co.uk/' },
            { label: 'Backend API Documentation (Swagger)', url: `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/docs` },
          ].map(link => (
            <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg
                         bg-navy-800 hover:bg-navy-750 border border-border-subtle
                         hover:border-border text-xs text-slate-300 hover:text-white
                         transition-all duration-150 group">
              <span>{link.label}</span>
              <ExternalLink size={12} className="text-slate-600 group-hover:text-accent-400 shrink-0" />
            </a>
          ))}
        </section>

        <p className="text-2xs text-slate-700 text-center pb-4">
          WindSight Analytics v1.0.0 · Data: Elexon BMRS · Period: January 2026
        </p>
      </div>
    </div>
  )
}
