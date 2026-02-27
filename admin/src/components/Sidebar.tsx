import { useLocation, useNavigate } from 'react-router-dom';

interface SidebarProps {
  username: string | null;
  onLogout: () => void;
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: DashboardIcon },
  { path: '/users', label: 'Users', icon: UsersIcon },
  { path: '/servers', label: 'Servers', icon: ServersIcon },
];

export function Sidebar({ username, onLogout }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <aside className="w-56 h-screen bg-gray-900 border-r border-gray-800 flex flex-col fixed left-0 top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white">VPNCraft</h1>
        <p className="text-xs text-gray-500 mt-0.5">Admin Panel</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-3 space-y-1">
        {navItems.map((item) => {
          const active = location.pathname === item.path;
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
              }`}
            >
              <item.icon />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* User / Logout */}
      <div className="px-3 pb-4 border-t border-gray-800 pt-3">
        {username && (
          <p className="text-xs text-gray-500 mb-2 px-3 truncate">@{username}</p>
        )}
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors"
        >
          <LogoutIcon />
          Logout
        </button>
      </div>
    </aside>
  );
}

function DashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function ServersIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
      <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
      <line x1="6" y1="6" x2="6.01" y2="6" />
      <line x1="6" y1="18" x2="6.01" y2="18" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}
