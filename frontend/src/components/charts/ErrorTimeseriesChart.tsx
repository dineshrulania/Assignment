import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'
import type { TimeseriesPoint } from '@/api/types'
import { fmtMW, fmtDateTimeShort } from '@/lib/formatters'

interface Props { data: TimeseriesPoint[]; height?: number }

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as TimeseriesPoint
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[180px]">
      <p className="text-slate-400 border-b border-border-subtle pb-1 mb-1">{fmtDateTimeShort(d.start_time)} UTC</p>
      <div className="flex justify-between gap-4">
        <span className={d.error_mw > 0 ? 'text-rose-400' : 'text-cyan-400'}>Error</span>
        <span className="mono text-white font-semibold">{d.error_mw > 0 ? '+' : ''}{fmtMW(d.error_mw)}</span>
      </div>
      <div className="flex justify-between gap-4"><span className="text-cyan-400">Forecast</span><span className="mono text-slate-300">{fmtMW(d.forecast_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-emerald-400">Actual</span><span className="mono text-slate-300">{fmtMW(d.actual_mw)}</span></div>
    </div>
  )
}

export default function ErrorTimeseriesChart({ data, height = 220 }: Props) {
  if (!data.length) return null
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="start_time" tickFormatter={(v) => fmtDateTimeShort(v)}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.07)' }}
          tickLine={false} interval="preserveStartEnd" />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
        <Bar dataKey="error_mw" maxBarSize={6} radius={[1, 1, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.error_mw > 0 ? '#fb7185' : '#22d3ee'} fillOpacity={0.7} />
          ))}
        </Bar>
        <Line type="monotone" dataKey="error_mw" stroke="#fbbf24" strokeWidth={1}
          dot={false} name="Error trend" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
