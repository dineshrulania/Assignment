import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Brush, Area,
} from 'recharts'
import type { TimeseriesPoint } from '@/api/types'
import { fmtMW, fmtDateTimeShort, fmtTimeOnly } from '@/lib/formatters'

interface Props {
  data: TimeseriesPoint[]
  showBrush?: boolean
  height?: number
  compact?: boolean
}

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const f = payload.find((p: any) => p.dataKey === 'forecast_mw')?.value as number | undefined
  const a = payload.find((p: any) => p.dataKey === 'actual_mw')?.value as number | undefined
  const e = f != null && a != null ? f - a : null
  const ts = payload[0]?.payload?.start_time as string | undefined
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[180px]">
      <p className="text-slate-400 font-medium border-b border-border-subtle pb-1.5 mb-1">
        {fmtDateTimeShort(ts)} UTC
      </p>
      {f != null && (
        <div className="flex justify-between gap-6">
          <span className="text-cyan-400">Forecast</span>
          <span className="mono text-white">{fmtMW(f)}</span>
        </div>
      )}
      {a != null && (
        <div className="flex justify-between gap-6">
          <span className="text-emerald-400">Actual</span>
          <span className="mono text-white">{fmtMW(a)}</span>
        </div>
      )}
      {e != null && (
        <div className="flex justify-between gap-6 border-t border-border-subtle pt-1 mt-1">
          <span className="text-slate-500">Error</span>
          <span className={`mono font-semibold ${e > 0 ? 'text-rose-400' : 'text-cyan-400'}`}>
            {e > 0 ? '+' : ''}{fmtMW(e)}
          </span>
        </div>
      )}
    </div>
  )
}

export default function ForecastVsActualChart({ data, showBrush = false, height = 280, compact = false }: Props) {
  if (!data.length) return null
  const fmt = compact ? (v: string) => fmtTimeOnly(v) : (v: string) => fmtDateTimeShort(v)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="fvAGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#f43f5e" stopOpacity={0.12} />
            <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="start_time" tickFormatter={fmt}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.07)' }}
          tickLine={false} interval="preserveStartEnd" />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(v) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
        <Area type="monotone" dataKey="forecast_mw" fill="url(#fvAGrad)" stroke="none" legendType="none" />
        <Line type="monotone" dataKey="forecast_mw" stroke="#22d3ee" strokeWidth={1.5}
          dot={false} name="Forecast" activeDot={{ r: 3, fill: '#22d3ee' }} />
        <Line type="monotone" dataKey="actual_mw" stroke="#34d399" strokeWidth={1.5}
          dot={false} name="Actual" activeDot={{ r: 3, fill: '#34d399' }} />
        {showBrush && (
          <Brush dataKey="start_time" height={22} stroke="rgba(255,255,255,0.07)"
            fill="#0a1628" tickFormatter={fmt} travellerWidth={6} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  )
}
