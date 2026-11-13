import { useEffect, useState } from 'react';
import { CalendarDays, RefreshCw, Wifi, WifiOff, Loader2 } from 'lucide-react';
import { format } from 'date-fns';
import { fetchHealth } from '@/api/client';
import type { HealthResponse } from '@/api/types';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const checkHealth = () => {
    setChecking(true);
    fetchHealth()
      .then((h) => { setHealth(h); setLastUpdated(new Date()); })
      .catch(() => setHealth(null))
      .finally(() => setChecking(false));
  };

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 60_000);
    return () => clearInterval(id);
  }, []);

  const isOk = health?.status === 'ok';

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4
                       px-6 py-3 bg-navy-900/90 backdrop-blur-sm
                       border-b border-border-subtle">
      {/* Page title */}
      <div className="min-w-0">
        <h1 className="text-base font-semibold text-white truncate">{title}</h1>
        {subtitle && (
          <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>
        )}
      </div>

      {/* Right cluster */}
      <div className="flex items-center gap-4 shrink-0">
        {/* Date */}
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-400">
          <CalendarDays size={13} className="text-slate-500" />
          <span>Jan 2026</span>
        </div>

        {/* Last updated */}
        <div className="hidden lg:flex items-center gap-2 text-xs text-slate-500">
          <RefreshCw size={12} />
          <span>Updated {format(lastUpdated, 'HH:mm:ss')}</span>
        </div>

        {/* Connection status */}
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
                     border transition-all duration-200 cursor-pointer"
          style={{
            background: isOk ? 'rgba(16,185,129,0.08)' : 'rgba(244,63,94,0.08)',
            borderColor: isOk ? 'rgba(16,185,129,0.25)' : 'rgba(244,63,94,0.25)',
            color: isOk ? '#34d399' : '#fb7185',
          }}
          onClick={checkHealth}
          title="Click to refresh connection status"
        >
          {checking ? (
            <Loader2 size={12} className="animate-spin" />
          ) : isOk ? (
            <Wifi size={12} />
          ) : (
            <WifiOff size={12} />
          )}
          <span className="hidden sm:inline">
            {checking ? 'Checking…' : isOk ? 'Live Data' : 'Disconnected'}
          </span>
          {isOk && health?.actuals_rows && (
            <span className="hidden lg:inline text-slate-500">
              · {health.actuals_rows.toLocaleString()} rows
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
