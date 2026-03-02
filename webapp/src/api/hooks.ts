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
