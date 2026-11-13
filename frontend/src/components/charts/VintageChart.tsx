import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import type { ForecastRecord } from '@/api/types'
import { fmtMW, fmtDateTimeShort } from '@/lib/formatters'

interface Props {
  data: ForecastRecord[]
  actualMw?: number
  height?: number
}

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as ForecastRecord
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[180px]">
      <p className="text-slate-400 border-b border-border-subtle pb-1 mb-1">Published {fmtDateTimeShort(d.publish_time)}</p>
      <div className="flex justify-between gap-4"><span className="text-cyan-400">Forecast</span><span className="mono text-white">{fmtMW(d.generation_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-500">Lead</span><span className="mono text-slate-300">{d.lead_hours.toFixed(1)}h</span></div>
    </div>
  )
}

export default function VintageChart({ data, actualMw, height = 220 }: Props) {
  if (!data.length) return null
  const sorted = [...data].sort((a, b) => new Date(a.publish_time).getTime() - new Date(b.publish_time).getTime())
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={sorted} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="publish_time" tickFormatter={(v) => fmtDateTimeShort(v)}
          tick={{ fill: '#64748b', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.07)' }}
          tickLine={false} interval="preserveStartEnd" />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} />
        {actualMw != null && (
          <ReferenceLine y={actualMw} stroke="#34d399" strokeDasharray="4 2"
            label={{ value: 'Actual', fill: '#34d399', fontSize: 10, position: 'insideTopRight' }} />
        )}
        <Line type="monotone" dataKey="generation_mw" stroke="#22d3ee" strokeWidth={2}
          dot={{ r: 2, fill: '#22d3ee', strokeWidth: 0 }} name="Forecast" />
      </LineChart>
    </ResponsiveContainer>
  )
}
