const API_BASE = import.meta.env.VITE_API_URL || '';

export class ApiRequestError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

export async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const token = localStorage.getItem('admin_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      ...headers,
      ...(opts?.headers as Record<string, string> || {}),
    },
  });

  if (res.status === 401) {
    // Token expired or invalid — clear auth
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    window.location.reload();
    throw new ApiRequestError(401, { error: 'Unauthorized' });
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = { error: res.statusText };
    }
    throw new ApiRequestError(res.status, body);
  }

  return res.json();
}
