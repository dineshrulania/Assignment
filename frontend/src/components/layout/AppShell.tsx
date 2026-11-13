import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function AppShell() {
  return (
    <div className="flex min-h-screen bg-navy-950">
      <Sidebar />
      <div className="flex flex-col flex-1 pl-60 min-w-0">
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
