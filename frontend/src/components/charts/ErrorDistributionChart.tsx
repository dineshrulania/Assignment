import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts'
import type { ErrorBin } from '@/api/types'

interface Props {
  bins: ErrorBin[]
  meanError: number
  height?: number
}

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const b = payload[0].payload as ErrorBin
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl">
      <p className="text-slate-400 border-b border-border-subtle pb-1 mb-1">{b.bin_label} MW</p>
      <div className="flex justify-between gap-4"><span className="text-slate-300">Count</span><span className="mono text-white">{b.count}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-300">Share</span><span className="mono text-white">{b.pct_of_total.toFixed(1)}%</span></div>
    </div>
  )
}

export default function ErrorDistributionChart({ bins, meanError, height = 220 }: Props) {
  if (!bins.length) return null
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={bins} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="bin_min_mw" tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          tick={{ fill: '#64748b', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.07)' }} tickLine={false} interval={3} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
        <Tooltip content={<TooltipContent />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 2" />
        <ReferenceLine x={meanError} stroke="#fbbf24" strokeDasharray="4 2"
          label={{ value: 'Mean', fill: '#fbbf24', fontSize: 10, position: 'top' }} />
        <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={22}>
          {bins.map((b, i) => (
            <Cell key={i} fill={b.bin_min_mw < 0 ? '#22d3ee' : '#fb7185'} fillOpacity={0.75} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
