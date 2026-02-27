import { retrieveRawInitData } from '@telegram-apps/sdk-react';

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
  let initDataRaw = '';
  try {
    initDataRaw = retrieveRawInitData() || '';
  } catch {
    // Outside Telegram — use mock in dev
    initDataRaw = import.meta.env.VITE_MOCK_INIT_DATA || '';
  }

  const headers: Record<string, string> = {
    'Authorization': `tma ${initDataRaw}`,
    'Content-Type': 'application/json',
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      ...headers,
      ...(opts?.headers as Record<string, string> || {}),
    },
  });

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
