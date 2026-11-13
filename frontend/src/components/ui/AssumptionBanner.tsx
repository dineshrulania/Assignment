import { AlertCircle, X } from 'lucide-react';
import { useState } from 'react';

interface Props {
  note?: string;
}

export default function AssumptionBanner({ note }: Props) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed || !note) return null;
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-lg
                    bg-amber-500/8 border border-amber-500/20 text-xs text-amber-300/80 animate-fade-in">
      <AlertCircle size={14} className="shrink-0 mt-0.5 text-amber-400" />
      <span className="flex-1 leading-relaxed">{note}</span>
      <button onClick={() => setDismissed(true)} className="shrink-0 text-amber-400/50 hover:text-amber-400">
        <X size={13} />
      </button>
    </div>
  );
}
