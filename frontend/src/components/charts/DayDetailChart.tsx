import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { DayDetailInterval } from '@/api/types'
import { fmtMW } from '@/lib/formatters'

interface Props { data: DayDetailInterval[]; height?: number }

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as DayDetailInterval
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[200px]">
      <p className="text-slate-300 font-medium border-b border-border-subtle pb-1 mb-1">{d.hour_utc} UTC</p>
      {d.forecast_mw != null && <div className="flex justify-between gap-4"><span className="text-cyan-400">Forecast</span><span className="mono text-white">{fmtMW(d.forecast_mw)}</span></div>}
      {d.actual_mw_on_hour != null && <div className="flex justify-between gap-4"><span className="text-emerald-400">Actual (HH:00)</span><span className="mono text-white">{fmtMW(d.actual_mw_on_hour)}</span></div>}
      {d.actual_mw_half_hour != null && <div className="flex justify-between gap-4"><span className="text-emerald-400/50">Actual (HH:30)</span><span className="mono text-slate-400">{fmtMW(d.actual_mw_half_hour)}</span></div>}
      {d.error_mw != null && (
        <div className="flex justify-between gap-4 border-t border-border-subtle pt-1 mt-1">
          <span className="text-slate-400">Error</span>
          <span className={`mono font-semibold ${d.error_mw > 0 ? 'text-rose-400' : 'text-cyan-400'}`}>
            {d.error_mw > 0 ? '+' : ''}{fmtMW(d.error_mw)}
          </span>
        </div>
      )}
      {d.forecast_publish_time && <p className="text-slate-600 mt-1">Published: {d.forecast_publish_time.slice(0, 16).replace('T', ' ')} UTC</p>}
    </div>
  )
}

export default function DayDetailChart({ data, height = 300 }: Props) {
  if (!data.length) return null
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="hour_utc" tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={{ stroke: 'rgba(255,255,255,0.07)' }} tickLine={false} />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(v) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
        <Bar dataKey="actual_mw_half_hour" fill="#34d399" fillOpacity={0.18}
          maxBarSize={18} name="Actual HH:30" />
        <Bar dataKey="actual_mw_on_hour" fill="#34d399" fillOpacity={0.55}
          maxBarSize={18} name="Actual HH:00" />
        <Line type="monotone" dataKey="forecast_mw" stroke="#22d3ee" strokeWidth={2}
          dot={{ r: 3, fill: '#22d3ee', strokeWidth: 0 }} name="Forecast" connectNulls />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
