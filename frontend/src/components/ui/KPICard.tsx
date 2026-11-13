import type { LucideIcon } from 'lucide-react';

interface Props {
  label: string;
  value: string | React.ReactNode;
  subvalue?: string;
  icon?: LucideIcon;
  iconColor?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  accent?: 'blue' | 'emerald' | 'amber' | 'rose' | 'cyan';
  loading?: boolean;
}

const accentMap = {
  blue:    { ring: 'ring-accent-500/20',  icon: 'bg-accent-500/10 text-accent-400' },
  emerald: { ring: 'ring-emerald-500/20', icon: 'bg-emerald-500/10 text-emerald-400' },
  amber:   { ring: 'ring-amber-500/20',   icon: 'bg-amber-500/10 text-amber-400' },
  rose:    { ring: 'ring-rose-500/20',    icon: 'bg-rose-500/10 text-rose-400' },
  cyan:    { ring: 'ring-cyan-500/20',    icon: 'bg-cyan-500/10 text-cyan-400' },
};

export default function KPICard({
  label,
  value,
  subvalue,
  icon: Icon,
  accent = 'blue',
  trend,
  trendLabel,
  loading = false,
}: Props) {
  const a = accentMap[accent];

  return (
    <div className={`card p-5 ring-1 ${a.ring} animate-fade-in`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider truncate">
            {label}
          </p>
          <div className="mt-2">
            {loading ? (
              <div className="h-7 w-32 bg-navy-800 animate-pulse rounded" />
            ) : (
              <div className="text-2xl font-semibold text-white mono leading-none">
                {value}
              </div>
            )}
          </div>
          {!loading && subvalue && (
            <p className="mt-1.5 text-xs text-slate-500">{subvalue}</p>
          )}
          {!loading && trendLabel && (
            <p
              className={`mt-1.5 text-xs font-medium ${
                trend === 'up'
                  ? 'text-rose-400'
                  : trend === 'down'
                  ? 'text-emerald-400'
                  : 'text-slate-500'
              }`}
            >
              {trendLabel}
            </p>
          )}
        </div>
        {Icon && (
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${a.icon}`}>
            <Icon size={18} />
          </div>
        )}
      </div>
    </div>
  );
}
