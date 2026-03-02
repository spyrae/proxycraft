import { useLocation, useNavigate } from 'react-router-dom';
import { useMemo } from 'react';

interface TabDef {
  path: string;
  label: string;
  icon: (props: { active: boolean }) => React.ReactElement;
}

const tabs: TabDef[] = [
  { path: '/', label: 'Home', icon: HomeIcon },
  { path: '/plans', label: 'Plans', icon: PlansIcon },
  { path: '/my-vpn', label: 'My VPN', icon: VpnIcon },
];

export function BottomTabs() {
  const location = useLocation();
  const navigate = useNavigate();

  const activeIndex = useMemo(
    () => tabs.findIndex((t) => t.path === location.pathname),
    [location.pathname],
  );

  const handleTap = (path: string) => {
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
      }
    } catch {}
    navigate(path);
  };

  return (
    <nav className="fixed bottom-4 left-4 right-4 z-50">
      <div
        className="glass flex justify-around items-center h-14 rounded-2xl"
        style={{
          border: '1px solid rgba(16, 185, 129, 0.15)',
          boxShadow: '0 4px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(16, 185, 129, 0.08)',
        }}
      >
        {tabs.map((tab, i) => {
          const active = i === activeIndex;
          return (
            <button
              key={tab.path}
              onClick={() => handleTap(tab.path)}
              className="flex flex-col items-center justify-center flex-1 h-full gap-0.5 relative transition-all duration-200"
              style={{ color: active ? '#10B981' : '#6B7280' }}
            >
              <tab.icon active={active} />
              <span
                className="text-[10px] font-semibold transition-all duration-200"
                style={{ opacity: active ? 1 : 0.7 }}
              >
                {tab.label}
              </span>
              {active && (
                <span
                  className="absolute -bottom-0 w-5 h-0.5 rounded-full"
                  style={{
                    backgroundColor: '#10B981',
                    boxShadow: '0 0 6px rgba(16, 185, 129, 0.6)',
                  }}
                />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

function HomeIcon({ active }: { active: boolean }) {
  if (active) {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 3l9 7v11a1 1 0 01-1 1h-5v-7h-6v7H4a1 1 0 01-1-1V10l9-7z" />
      </svg>
    );
  }
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function PlansIcon({ active }: { active: boolean }) {
  if (active) {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
        <rect x="2" y="3" width="20" height="14" rx="3" />
        <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
      </svg>
    );
  }
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function VpnIcon({ active }: { active: boolean }) {
  if (active) {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="M9 12l2 2 4-4" stroke="#0A0E17" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
    );
  }
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

// Augment window for Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        HapticFeedback?: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
        };
      };
    };
  }
}
