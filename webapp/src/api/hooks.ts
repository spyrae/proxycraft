import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  UserProfile,
  VpnPlan,
  ServicePlan,
  VpnSubscription,
  MtprotoSubscription,
  WhatsappSubscription,
  InvoiceResponse,
  TrialVpnResponse,
  TrialMtprotoResponse,
  TrialWhatsappResponse,
  PromocodeResponse,
  TopupResponse,
  BuyPlanResponse,
  AutoRenewResponse,
  CancelSubscriptionResponse,
  ChangeVpnProfileResponse,
} from './types';

// ---------- Queries ----------

export function useMe() {
  return useQuery<UserProfile>({
    queryKey: ['me'],
    queryFn: () => api('/api/v1/me'),
    staleTime: 60_000,
  });
}

export function usePlans() {
  return useQuery<{ plans: VpnPlan[] }>({
    queryKey: ['plans'],
    queryFn: () => api('/api/v1/plans'),
    staleTime: 5 * 60_000,
  });
}

export function useMtprotoPlans() {
  return useQuery<{ plans: ServicePlan[] }>({
    queryKey: ['plans', 'mtproto'],
    queryFn: () => api('/api/v1/plans/mtproto'),
    staleTime: 5 * 60_000,
  });
}

export function useWhatsappPlans() {
  return useQuery<{ plans: ServicePlan[] }>({
    queryKey: ['plans', 'whatsapp'],
    queryFn: () => api('/api/v1/plans/whatsapp'),
    staleTime: 5 * 60_000,
  });
}

export function useLocations() {
  return useQuery<{ locations: { name: string; available: boolean }[] }>({
    queryKey: ['locations'],
    queryFn: () => api('/api/v1/locations'),
    staleTime: 5 * 60_000,
  });
}

export function useVpnSubscription() {
  return useQuery<VpnSubscription>({
    queryKey: ['subscription', 'vpn'],
    queryFn: () => api('/api/v1/subscription'),
    staleTime: 60_000,
  });
}

export function useMtprotoSubscription() {
  return useQuery<MtprotoSubscription>({
    queryKey: ['subscription', 'mtproto'],
    queryFn: () => api('/api/v1/subscription/mtproto'),
    staleTime: 60_000,
  });
}

export function useWhatsappSubscription() {
  return useQuery<WhatsappSubscription>({
    queryKey: ['subscription', 'whatsapp'],
    queryFn: () => api('/api/v1/subscription/whatsapp'),
    staleTime: 60_000,
  });
}

// ---------- Mutations ----------

interface InvoiceParams {
  product: 'vpn' | 'mtproto' | 'whatsapp';
  devices?: number;
  duration: number;
  is_extend?: boolean;
  currency?: 'stars' | 'rub';
}

export function useCreateInvoice() {
  return useMutation<InvoiceResponse, Error, InvoiceParams>({
    mutationFn: (params) =>
      api('/api/v1/payment/invoice', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  });
}

export function useTrialVpn() {
  const qc = useQueryClient();
  return useMutation<TrialVpnResponse, Error>({
    mutationFn: () => api('/api/v1/trial/vpn', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'vpn'] });
    },
  });
}

export function useTrialMtproto() {
  const qc = useQueryClient();
  return useMutation<TrialMtprotoResponse, Error>({
    mutationFn: () => api('/api/v1/trial/mtproto', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'mtproto'] });
    },
  });
}

export function useTrialWhatsapp() {
  const qc = useQueryClient();
  return useMutation<TrialWhatsappResponse, Error>({
    mutationFn: () => api('/api/v1/trial/whatsapp', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'whatsapp'] });
    },
  });
}

export function useActivatePromocode() {
  const qc = useQueryClient();
  return useMutation<PromocodeResponse, Error, { code: string }>({
    mutationFn: ({ code }) =>
      api('/api/v1/promocode/activate', {
        method: 'POST',
        body: JSON.stringify({ code }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'vpn'] });
    },
  });
}

// ---------- Balance ----------

interface TopupParams {
  amount: number;
  currency: 'stars' | 'rub' | 'sbp';
}

export function useTopup() {
  return useMutation<TopupResponse, Error, TopupParams>({
    mutationFn: (params) =>
      api('/api/v1/balance/topup', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  });
}

interface BuyPlanParams {
  product: 'vpn' | 'mtproto' | 'whatsapp';
  devices?: number;
  duration: number;
  location?: string;
}

export function useBuyPlan() {
  const qc = useQueryClient();
  return useMutation<BuyPlanResponse, Error, BuyPlanParams>({
    mutationFn: (params) =>
      api('/api/v1/plans/buy', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription'] });
    },
  });
}

export function useAutoRenew() {
  const qc = useQueryClient();
  return useMutation<AutoRenewResponse, Error, { enabled: boolean }>({
    mutationFn: ({ enabled }) =>
      api('/api/v1/balance/auto-renew', {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}

export function useCancelSubscription() {
  const qc = useQueryClient();
  return useMutation<CancelSubscriptionResponse, Error, { product: 'vpn' | 'mtproto' | 'whatsapp' }>({
    mutationFn: ({ product }) =>
      api('/api/v1/subscription/cancel', {
        method: 'POST',
        body: JSON.stringify({ product }),
      }),
    onSuccess: (_, { product }) => {
      qc.invalidateQueries({ queryKey: ['subscription', product] });
    },
  });
}

export function useChangeVpnProfile() {
  const qc = useQueryClient();
  return useMutation<ChangeVpnProfileResponse, Error, { profileSlug: string }>({
    mutationFn: ({ profileSlug }) =>
      api('/api/v1/subscription/vpn-profile', {
        method: 'POST',
        body: JSON.stringify({ profile_slug: profileSlug }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'vpn'] });
    },
  });
}
