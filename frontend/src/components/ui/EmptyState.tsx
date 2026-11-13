import { InboxIcon } from 'lucide-react';

interface Props {
  title?: string;
  message?: string;
  action?: React.ReactNode;
}

export default function EmptyState({
  title = 'No data',
  message = 'No records found for the selected period.',
  action,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full
                      bg-navy-800 ring-1 ring-border">
        <InboxIcon size={22} className="text-slate-500" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-400">{title}</p>
        <p className="mt-1 text-xs text-slate-600 max-w-xs">{message}</p>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
