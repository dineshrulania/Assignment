type Variant = 'ok' | 'warning' | 'error' | 'neutral' | 'info';

interface Props {
  variant?: Variant;
  label: string;
  dot?: boolean;
}

const variantMap: Record<Variant, string> = {
  ok:      'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25',
  warning: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/25',
  error:   'bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/25',
  neutral: 'bg-navy-800 text-slate-400 ring-1 ring-border',
  info:    'bg-accent-500/10 text-accent-400 ring-1 ring-accent-500/25',
};
const dotMap: Record<Variant, string> = {
  ok:      'bg-emerald-400',
  warning: 'bg-amber-400',
  error:   'bg-rose-400',
  neutral: 'bg-slate-500',
  info:    'bg-accent-400',
};

export default function StatusBadge({ variant = 'neutral', label, dot = true }: Props) {
  return (
    <span className={`badge ${variantMap[variant]}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotMap[variant]}`} />}
      {label}
    </span>
  );
}
