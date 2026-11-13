import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Wind,
  BarChart3,
  Database,
  Settings,
  Zap,
} from 'lucide-react';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { to: '/',          icon: <LayoutDashboard size={18} />, label: 'Overview' },
  { to: '/forecast',  icon: <Wind size={18} />,            label: 'Forecast Explorer' },
  { to: '/accuracy',  icon: <BarChart3 size={18} />,       label: 'Accuracy Analysis' },
  { to: '/data',      icon: <Database size={18} />,        label: 'Data Explorer' },
  { to: '/settings',  icon: <Settings size={18} />,        label: 'Settings' },
];

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-navy-900 border-r border-border-subtle">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border-subtle">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-500/20 ring-1 ring-accent-500/40">
          <Zap size={16} className="text-accent-400" />
        </div>
        <div>
          <span className="block text-sm font-semibold text-white tracking-tight">WindSight</span>
          <span className="block text-2xs text-slate-500 tracking-widest uppercase">Analytics</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        <p className="section-label px-2 mb-3">Navigation</p>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group',
                isActive
                  ? 'bg-accent-500/15 text-accent-400 ring-1 ring-accent-500/25'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-800',
              ].join(' ')
            }
          >
            <span className="shrink-0">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge && (
              <span className="badge bg-accent-500/20 text-accent-400 text-2xs">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border-subtle">
        <p className="text-2xs text-slate-600 leading-relaxed">
          Data: Elexon BMRS
          <br />
          Period: Jan 2026
        </p>
      </div>
    </aside>
  );
}
