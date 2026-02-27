import { useLocation, useNavigate } from 'react-router-dom';

interface TabDef {
  path: string;
  label: string;
  icon: (props: { active: boolean }) => JSX.Element;
}

const tabs: TabDef[] = [
  { path: '/', label: 'Home', icon: HomeIcon },
  { path: '/plans', label: 'Plans', icon: PlansIcon },
  { path: '/my-vpn', label: 'My VPN', icon: VpnIcon },
];

export function BottomTabs() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex justify-around items-center h-14 border-t z-50"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderColor: 'var(--divider)',
      }}
    >
      {tabs.map((tab) => {
        const active = location.pathname === tab.path;
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            className="flex flex-col items-center justify-center flex-1 h-full gap-0.5"
            style={{ color: active ? 'var(--accent)' : 'var(--text-hint)' }}
          >
            <tab.icon active={active} />
            <span className="text-[10px] font-medium">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function HomeIcon({ active }: { active: boolean }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function PlansIcon({ active }: { active: boolean }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function VpnIcon({ active }: { active: boolean }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
