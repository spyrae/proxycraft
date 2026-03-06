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
  SubscriptionsResponse,
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

export function useSubscriptions() {
  return useQuery<SubscriptionsResponse>({
    queryKey: ['subscriptions'],
    queryFn: () => api('/api/v1/subscriptions'),
    staleTime: 60_000,
  });
}

export function useVpnSubscriptions() {
  return useQuery<{ subscriptions: VpnSubscription[] }>({
    queryKey: ['subscriptions', 'vpn'],
    queryFn: () => api('/api/v1/subscriptions/vpn'),
    staleTime: 60_000,
  });
}

export function useMtprotoSubscriptions() {
  return useQuery<{ subscriptions: MtprotoSubscription[] }>({
    queryKey: ['subscriptions', 'mtproto'],
    queryFn: () => api('/api/v1/subscriptions/mtproto'),
    staleTime: 60_000,
  });
}

export function useWhatsappSubscriptions() {
  return useQuery<{ subscriptions: WhatsappSubscription[] }>({
    queryKey: ['subscriptions', 'whatsapp'],
    queryFn: () => api('/api/v1/subscriptions/whatsapp'),
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
      qc.invalidateQueries({ queryKey: ['me'], refetchType: 'all' });
      qc.invalidateQueries({ queryKey: ['subscription', 'vpn'], refetchType: 'all' });
    },
  });
}

export function useTrialMtproto() {
  const qc = useQueryClient();
  return useMutation<TrialMtprotoResponse, Error>({
    mutationFn: () => api('/api/v1/trial/mtproto', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'], refetchType: 'all' });
      qc.invalidateQueries({ queryKey: ['subscription', 'mtproto'], refetchType: 'all' });
    },
  });
}

export function useTrialWhatsapp() {
  const qc = useQueryClient();
  return useMutation<TrialWhatsappResponse, Error>({
    mutationFn: () => api('/api/v1/trial/whatsapp', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'], refetchType: 'all' });
      qc.invalidateQueries({ queryKey: ['subscription', 'whatsapp'], refetchType: 'all' });
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
      qc.invalidateQueries({ queryKey: ['me'], refetchType: 'all' });
      qc.invalidateQueries({ queryKey: ['subscription'], refetchType: 'all' });
      qc.invalidateQueries({ queryKey: ['subscriptions'], refetchType: 'all' });
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
  return useMutation<
    CancelSubscriptionResponse,
    Error,
    { product: 'vpn' | 'mtproto' | 'whatsapp'; subscriptionId?: number | null }
  >({
    mutationFn: ({ product, subscriptionId }) =>
      api('/api/v1/subscription/cancel', {
        method: 'POST',
        body: JSON.stringify({
          product,
          subscription_id: subscriptionId ?? undefined,
        }),
      }),
    onSuccess: (_, { product }) => {
      qc.invalidateQueries({ queryKey: ['subscription', product] });
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['subscriptions', product] });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}

export function useChangeVpnProfile() {
  const qc = useQueryClient();
  return useMutation<
    ChangeVpnProfileResponse,
    Error,
    { profileSlug: string; subscriptionId?: number | null },
    {
      previousSubscription?: VpnSubscription;
      previousMe?: UserProfile;
      previousSubscriptions?: SubscriptionsResponse;
      previousVpnSubscriptions?: { subscriptions: VpnSubscription[] };
    }
  >({
    mutationFn: ({ profileSlug, subscriptionId }) =>
      api('/api/v1/subscription/vpn-profile', {
        method: 'POST',
        body: JSON.stringify({
          profile_slug: profileSlug,
          subscription_id: subscriptionId ?? undefined,
        }),
      }),
    onMutate: async ({ profileSlug, subscriptionId }) => {
      await qc.cancelQueries({ queryKey: ['subscription', 'vpn'] });
      await qc.cancelQueries({ queryKey: ['subscriptions'] });

      const previousSubscription = qc.getQueryData<VpnSubscription>(['subscription', 'vpn']);
      const previousMe = qc.getQueryData<UserProfile>(['me']);
      const previousSubscriptions = qc.getQueryData<SubscriptionsResponse>(['subscriptions']);
      const previousVpnSubscriptions = qc.getQueryData<{ subscriptions: VpnSubscription[] }>(['subscriptions', 'vpn']);

      if (previousSubscription) {
        const nextProfile = previousSubscription.available_profiles?.find(
          (profile) => profile.slug === profileSlug,
        );

        qc.setQueryData<VpnSubscription>(['subscription', 'vpn'], {
          ...previousSubscription,
          current_profile: nextProfile ?? previousSubscription.current_profile ?? null,
        });
      }

      if (previousSubscriptions) {
        qc.setQueryData<SubscriptionsResponse>(['subscriptions'], {
          ...previousSubscriptions,
          vpn: previousSubscriptions.vpn.map((subscription) => {
            if ((subscription.subscription_id ?? null) !== (subscriptionId ?? null)) {
              return subscription;
            }

            const nextProfile = subscription.available_profiles?.find(
              (profile) => profile.slug === profileSlug,
            );

            return {
              ...subscription,
              current_profile: nextProfile ?? subscription.current_profile ?? null,
            };
          }),
        });
      }

      if (previousVpnSubscriptions) {
        qc.setQueryData<{ subscriptions: VpnSubscription[] }>(['subscriptions', 'vpn'], {
          subscriptions: previousVpnSubscriptions.subscriptions.map((subscription) => {
            if ((subscription.subscription_id ?? null) !== (subscriptionId ?? null)) {
              return subscription;
            }

            const nextProfile = subscription.available_profiles?.find(
              (profile) => profile.slug === profileSlug,
            );

            return {
              ...subscription,
              current_profile: nextProfile ?? subscription.current_profile ?? null,
            };
          }),
        });
      }

      if (previousMe) {
        qc.setQueryData<UserProfile>(['me'], {
          ...previousMe,
          vpn_profile_slug: profileSlug,
        });
      }

      return { previousSubscription, previousMe, previousSubscriptions, previousVpnSubscriptions };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousSubscription) {
        qc.setQueryData(['subscription', 'vpn'], context.previousSubscription);
      }

      if (context?.previousSubscriptions) {
        qc.setQueryData(['subscriptions'], context.previousSubscriptions);
      }

      if (context?.previousVpnSubscriptions) {
        qc.setQueryData(['subscriptions', 'vpn'], context.previousVpnSubscriptions);
      }

      if (context?.previousMe) {
        qc.setQueryData(['me'], context.previousMe);
      }
    },
    onSuccess: (data) => {
      qc.setQueryData(['subscription', 'vpn'], data);

      const previousSubscriptions = qc.getQueryData<SubscriptionsResponse>(['subscriptions']);
      if (previousSubscriptions && data.subscription_id != null) {
        qc.setQueryData<SubscriptionsResponse>(['subscriptions'], {
          ...previousSubscriptions,
          vpn: previousSubscriptions.vpn.map((subscription) =>
            subscription.subscription_id === data.subscription_id ? data : subscription,
          ),
        });
      }

      const previousVpnSubscriptions = qc.getQueryData<{ subscriptions: VpnSubscription[] }>(['subscriptions', 'vpn']);
      if (previousVpnSubscriptions && data.subscription_id != null) {
        qc.setQueryData<{ subscriptions: VpnSubscription[] }>(['subscriptions', 'vpn'], {
          subscriptions: previousVpnSubscriptions.subscriptions.map((subscription) =>
            subscription.subscription_id === data.subscription_id ? data : subscription,
          ),
        });
      }

      const previousMe = qc.getQueryData<UserProfile>(['me']);
      if (previousMe) {
        qc.setQueryData<UserProfile>(['me'], {
          ...previousMe,
          vpn_profile_slug: data.current_profile?.slug ?? null,
        });
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['subscription', 'vpn'] });
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['subscriptions', 'vpn'] });
    },
  });
}
