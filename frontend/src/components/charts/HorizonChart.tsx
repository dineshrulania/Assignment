import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { HorizonBucket } from '@/api/types'
import { fmtMW } from '@/lib/formatters'

interface Props { data: HorizonBucket[]; height?: number }

function TooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const b = payload[0].payload as HorizonBucket
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1 shadow-xl min-w-[160px]">
      <p className="text-slate-300 font-medium border-b border-border-subtle pb-1 mb-1">{b.bucket_label}</p>
      <div className="flex justify-between gap-4"><span className="text-amber-400">MAE</span><span className="mono text-white">{fmtMW(b.mae_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-rose-400">RMSE</span><span className="mono text-white">{fmtMW(b.rmse_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-400">Bias</span><span className={`mono ${b.mbe_mw > 0 ? 'text-rose-400' : 'text-cyan-400'}`}>{b.mbe_mw > 0 ? '+' : ''}{fmtMW(b.mbe_mw)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-slate-500">N</span><span className="mono text-slate-400">{b.n_intervals}</span></div>
    </div>
  )
}

export default function HorizonChart({ data, height = 220 }: Props) {
  if (!data.length) return null
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="bucket_label" tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={{ stroke: 'rgba(255,255,255,0.07)' }} tickLine={false} />
        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
        <Tooltip content={<TooltipContent />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(v) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
        <Line type="monotone" dataKey="mae_mw" stroke="#fbbf24" strokeWidth={2}
          dot={{ r: 3, fill: '#fbbf24' }} name="MAE" />
        <Line type="monotone" dataKey="rmse_mw" stroke="#fb7185" strokeWidth={2}
          dot={{ r: 3, fill: '#fb7185' }} name="RMSE" strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  )
}
