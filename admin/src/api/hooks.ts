import { useQuery } from '@tanstack/react-query';
import { api } from './client.ts';
import type {
  AdminStats,
  AdminUser,
  AdminUserDetail,
  AdminServer,
} from './types.ts';

export function useAdminStats() {
  return useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: () => api('/api/v1/admin/stats'),
    staleTime: 60_000,
  });
}

export function useAdminUsers(q: string = '', page: number = 1) {
  return useQuery<{ users: AdminUser[]; total: number; page: number; limit: number }>({
    queryKey: ['admin', 'users', q, page],
    queryFn: () => api(`/api/v1/admin/users?q=${encodeURIComponent(q)}&page=${page}&limit=20`),
    staleTime: 30_000,
  });
}

export function useAdminUser(tgId: number | null) {
  return useQuery<AdminUserDetail>({
    queryKey: ['admin', 'user', tgId],
    queryFn: () => api(`/api/v1/admin/users/${tgId}`),
    enabled: tgId !== null,
    staleTime: 30_000,
  });
}

export function useAdminServers() {
  return useQuery<{ servers: AdminServer[] }>({
    queryKey: ['admin', 'servers'],
    queryFn: () => api('/api/v1/admin/servers'),
    staleTime: 60_000,
  });
}
