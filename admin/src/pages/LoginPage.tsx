import { useState, useCallback } from 'react';
import { TelegramLogin } from '../components/TelegramLogin.tsx';
import type { TelegramLoginData } from '../api/types.ts';

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || 'vpncraft_bot';

interface LoginPageProps {
  onLogin: (data: TelegramLoginData) => Promise<void>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAuth = useCallback(async (data: TelegramLoginData) => {
    setError(null);
    setLoading(true);
    try {
      await onLogin(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }, [onLogin]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8 w-full max-w-sm text-center">
        {/* Logo / Title */}
        <div className="mb-6">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">VPNCraft Admin</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in with your Telegram account</p>
        </div>

        {/* Telegram Login Widget */}
        {loading ? (
          <div className="flex items-center justify-center h-12">
            <div className="animate-spin rounded-full h-6 w-6 border-2 border-indigo-500 border-t-transparent" />
          </div>
        ) : (
          <TelegramLogin botName={BOT_USERNAME} onAuth={handleAuth} />
        )}

        {/* Error message */}
        {error && (
          <div className="mt-4 text-sm text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Note */}
        <p className="text-xs text-gray-600 mt-6">
          Only authorized administrators can access this panel.
        </p>
      </div>
    </div>
  );
}
