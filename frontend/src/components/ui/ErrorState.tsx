import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  message?: string;
  onRetry?: () => void;
  fullHeight?: boolean;
}

export default function ErrorState({
  message = 'Failed to load data.',
  onRetry,
  fullHeight = false,
}: Props) {
  return (
    <div className={`flex flex-col items-center justify-center gap-4 text-center
                     ${fullHeight ? 'min-h-[320px]' : 'py-16'}`}>
      <div className="flex h-12 w-12 items-center justify-center rounded-full
                      bg-rose-500/10 ring-1 ring-rose-500/25">
        <AlertTriangle size={22} className="text-rose-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-300">Something went wrong</p>
        <p className="mt-1 text-xs text-slate-500 max-w-xs">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
