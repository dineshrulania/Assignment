import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import type { DailyMetrics } from '@/api/types'
import { fmtMW, fmtDate, maeHex } from '@/lib/formatters'

interface Props {
  data: DailyMetrics[]
  height?: number
  onDayClick?: (date: string) => void
}

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as DailyMetrics
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[160px]">
      <p className="text-slate-300 font-medium border-b border-border-subtle pb-1 mb-1">{fmtDate(d.settlement_date)}</p>
      <div className="flex justify-between gap-4"><span className="text-amber-400">MAE</span><span className="mono text-white">{fmtMW(d.mae_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-400">Bias</span><span className={`mono ${d.mbe_mw > 0 ? 'text-rose-400' : 'text-cyan-400'}`}>{d.mbe_mw > 0 ? '+' : ''}{fmtMW(d.mbe_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-400">Intervals</span><span className="mono text-slate-300">{d.n_intervals}</span></div>
    </div>
  )
}

export default function DailyMAEChart({ data, height = 220, onDayClick }: Props) {
  if (!data.length) return null
  const avg = data.reduce((s, d) => s + d.mae_mw, 0) / data.length
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
        onClick={onDayClick ? (e) => { if (e?.activePayload?.[0]) onDayClick((e.activePayload[0].payload as DailyMetrics).settlement_date) } : undefined}
        style={{ cursor: onDayClick ? 'pointer' : 'default' }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="settlement_date" tickFormatter={(v) => v.slice(8)}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.07)' }} tickLine={false} />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <ReferenceLine y={avg} stroke="rgba(251,191,36,0.4)" strokeDasharray="4 3"
          label={{ value: 'Avg', fill: '#fbbf24', fontSize: 10, position: 'insideTopRight' }} />
        <Bar dataKey="mae_mw" radius={[2, 2, 0, 0]} maxBarSize={28}>
          {data.map((entry) => (
            <Cell key={entry.settlement_date} fill={maeHex(entry.mae_mw)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
