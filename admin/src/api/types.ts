export interface AdminStats {
  total_users: number;
  active_subscriptions: number;
  revenue: Record<string, number>;
  registrations_30d: { date: string; count: number }[];
  payments_30d: { date: string; count: number }[];
}

export interface AdminUser {
  tg_id: number;
  first_name: string;
  username: string | null;
  created_at: string | null;
  server_name: string | null;
  is_trial_used: boolean;
}

export interface AdminTransaction {
  id: number;
  payment_id: string;
  subscription: string;
  status: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AdminUserDetail {
  tg_id: number;
  first_name: string;
  username: string | null;
  created_at: string | null;
  server_name: string | null;
  is_trial_used: boolean;
  vpn: {
    active: boolean;
    expired: boolean;
    max_devices: number;
    traffic_total: number;
    traffic_used: number;
    expiry_time: number;
  } | null;
  transactions: AdminTransaction[];
}

export interface AdminServer {
  id: number;
  name: string;
  host: string;
  location: string | null;
  online: boolean;
  max_clients: number;
  current_clients: number;
}

export interface AuthResponse {
  token: string;
  expires_in: number;
  user: {
    tg_id: number;
    first_name: string;
    username: string | null;
  };
}

export interface TelegramLoginData {
  id: number;
  first_name: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}
