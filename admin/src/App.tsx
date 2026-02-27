import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useAuth } from './hooks/useAuth.ts';
import { Sidebar } from './components/Sidebar.tsx';
import { LoginPage } from './pages/LoginPage.tsx';
import { DashboardPage } from './pages/DashboardPage.tsx';
import { UsersPage } from './pages/UsersPage.tsx';
import { ServersPage } from './pages/ServersPage.tsx';

export default function App() {
  const { isAuthenticated, user, login, logout } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950">
        <Sidebar username={user?.username ?? null} onLogout={logout} />

        {/* Main content — offset by sidebar width */}
        <main className="flex-1 ml-56 p-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/servers" element={<ServersPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
