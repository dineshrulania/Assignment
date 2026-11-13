import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
  pageSize: number;
  totalRows: number;
}

export default function Pagination({ page, totalPages, onPage, pageSize, totalRows }: Props) {
  const start = (page - 1) * pageSize + 1;
  const end   = Math.min(page * pageSize, totalRows);

  return (
    <div className="flex items-center justify-between gap-4 px-1">
      <span className="text-xs text-slate-500">
        {start}–{end} of {totalRows.toLocaleString()} rows
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="btn-ghost p-1.5 disabled:opacity-30"
        >
          <ChevronLeft size={15} />
        </button>
        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
          const p = i + 1;
          return (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={[
                'h-7 w-7 rounded text-xs font-medium transition-colors',
                p === page
                  ? 'bg-accent-500 text-white'
                  : 'text-slate-400 hover:bg-navy-800 hover:text-slate-200',
              ].join(' ')}
            >
              {p}
            </button>
          );
        })}
        {totalPages > 7 && (
          <span className="text-xs text-slate-600 px-1">…{totalPages}</span>
        )}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="btn-ghost p-1.5 disabled:opacity-30"
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}
