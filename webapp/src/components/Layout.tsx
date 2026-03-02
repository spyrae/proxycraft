import { Outlet } from 'react-router-dom';
import { BottomTabs } from './BottomTabs';

export function Layout() {
  return (
    <div className="flex flex-col min-h-screen pb-24" style={{ backgroundColor: 'var(--bg-secondary)' }}>
      <main className="flex-1 px-4 pt-3 pb-4">
        <Outlet />
      </main>
      <BottomTabs />
    </div>
  );
}
