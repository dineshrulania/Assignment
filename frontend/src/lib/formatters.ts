/**
 * Formatting utilities — all data display goes through these functions
 * so the presentation layer never does ad-hoc number manipulation.
 */

import { format, parseISO } from 'date-fns';

// ── Numbers ───────────────────────────────────────────────────────────────────

/** Format a MW value: "15,420 MW" */
export function fmtMW(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined) return '—';
  return `${value.toLocaleString('en-GB', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })} MW`;
}

/** Format a MW value as a compact number: "15.4k" */
export function fmtMWCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(1)}k MW`;
  }
  return `${Math.round(value)} MW`;
}

/** Format a percentage: "98.4%" */
export function fmtPct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(decimals)}%`;
}

/** Format a signed MW value with explicit +/- sign */
export function fmtSignedMW(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${Math.round(value).toLocaleString('en-GB')} MW`;
}

/** Format lead hours: "27.3h" */
export function fmtHours(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(1)}h`;
}

// ── Dates & times ─────────────────────────────────────────────────────────────

/** "2026-01-15" → "15 Jan 2026" */
export function fmtDate(isoDate: string | null | undefined): string {
  if (!isoDate) return '—';
  try {
    return format(parseISO(isoDate), 'd MMM yyyy');
  } catch {
    return isoDate;
  }
}

/** "2026-01-15T14:00:00Z" → "15 Jan 14:00" */
export function fmtDateTimeShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), 'd MMM HH:mm');
  } catch {
    return iso;
  }
}

/** "2026-01-15T14:00:00Z" → "15 Jan 2026 14:00 UTC" */
export function fmtDateTimeFull(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), "d MMM yyyy HH:mm 'UTC'");
  } catch {
    return iso ?? '—';
  }
}

/** "2026-01-15T14:00:00Z" → "14:00" */
export function fmtTimeOnly(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), 'HH:mm');
  } catch {
    return iso;
  }
}

/** "2026-01-15" → "Jan 15" (chart axis label) */
export function fmtAxisDate(isoDate: string | null | undefined): string {
  if (!isoDate) return '';
  try {
    return format(parseISO(isoDate), 'MMM d');
  } catch {
    return isoDate;
  }
}

// ── Colour helpers ────────────────────────────────────────────────────────────

/** Returns a Tailwind text colour class based on MAE severity */
export function maeColour(mae: number): string {
  if (mae < 500) return 'text-emerald-400';
  if (mae < 1500) return 'text-amber-400';
  return 'text-rose-400';
}

/** Returns a Tailwind text colour class for bias direction */
export function biasColour(mbe: number): string {
  if (Math.abs(mbe) < 100) return 'text-slate-300';
  return mbe > 0 ? 'text-rose-400' : 'text-cyan-400';
}

/** Returns a hex colour for recharts based on MAE severity */
export function maeHex(mae: number): string {
  if (mae < 500) return '#34d399';   // emerald-400
  if (mae < 1500) return '#fbbf24';  // amber-400
  return '#fb7185';                   // rose-400
}

// ── CSV export ────────────────────────────────────────────────────────────────

export function exportCSV(
  rows: Record<string, unknown>[],
  filename: string,
): void {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csvLines = [
    headers.join(','),
    ...rows.map((r) =>
      headers
        .map((h) => {
          const val = r[h];
          const str = val === null || val === undefined ? '' : String(val);
          return str.includes(',') ? `"${str}"` : str;
        })
        .join(','),
    ),
  ];
  const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
