import { Info } from 'lucide-react';

interface Props {
  value: number;
  onChange: (hour: number) => void;
  disabled?: boolean;
}

const OPTIONS = [7, 8, 9, 10, 11, 12];

export default function CutoffSelector({ value, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5">
        <Info size={12} className="text-slate-500 shrink-0" />
        <span className="text-xs text-slate-500">D-1 cutoff:</span>
      </div>
      <div className="flex gap-1">
        {OPTIONS.map((h) => (
          <button
            key={h}
            disabled={disabled}
            onClick={() => onChange(h)}
            className={[
              'px-2.5 py-1 rounded text-xs font-medium transition-all duration-150',
              value === h
                ? 'bg-accent-500 text-white'
                : 'bg-navy-800 text-slate-400 hover:text-slate-200 hover:bg-navy-700 border border-border',
            ].join(' ')}
          >
            {String(h).padStart(2, '0')}:00
          </button>
        ))}
      </div>
    </div>
  );
}
