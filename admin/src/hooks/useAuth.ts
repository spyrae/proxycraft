import { useState, useCallback } from 'react';
import type { AuthResponse, TelegramLoginData } from '../api/types.ts';

const API_BASE = import.meta.env.VITE_API_URL || '';

interface AuthUser {
  tg_id: number;
  first_name: string;
  username: string | null;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
}

function loadAuthState(): AuthState {
  const token = localStorage.getItem('admin_token');
  const userJson = localStorage.getItem('admin_user');
  let user: AuthUser | null = null;
  if (userJson) {
    try {
      user = JSON.parse(userJson);
    } catch {
      // corrupted data
    }
  }
  return { token, user };
}

export function useAuth() {
  const [state, setState] = useState<AuthState>(loadAuthState);

  const login = useCallback(async (loginData: TelegramLoginData) => {
    const res = await fetch(`${API_BASE}/api/v1/admin/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginData),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ error: 'Login failed' }));
      throw new Error((body as { error?: string }).error || `HTTP ${res.status}`);
    }

    const data: AuthResponse = await res.json();

    localStorage.setItem('admin_token', data.token);
    localStorage.setItem('admin_user', JSON.stringify(data.user));
    setState({ token: data.token, user: data.user });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    setState({ token: null, user: null });
  }, []);

  return {
    isAuthenticated: !!state.token,
    user: state.user,
    login,
    logout,
  };
}
