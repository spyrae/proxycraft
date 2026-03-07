import type { Page, Route } from '@playwright/test';
import type {
  MtprotoSubscription,
  UserProfile,
  VpnProfileOption,
  VpnSubscription,
  WhatsappSubscription,
} from '../../../src/api/types';

type DelayMap = Partial<Record<
  'me'
  | 'subscriptions'
  | 'vpnSubscriptions'
  | 'mtprotoSubscriptions'
  | 'whatsappSubscriptions'
  | 'changeVpnProfile'
  | 'acceptConsents',
  number
>>;

type MockApiOptions = {
  me?: UserProfile;
  vpnSubscriptions?: VpnSubscription[];
  mtprotoSubscriptions?: MtprotoSubscription[];
  whatsappSubscriptions?: WhatsappSubscription[];
  delays?: DelayMap;
};

function createDefaultMe(requiredConsentsAccepted: boolean): UserProfile {
  return {
    tg_id: 9990001,
    first_name: 'Playwright',
    username: 'playwright_user',
    created_at: '2026-03-07T00:00:00Z',
    is_admin: false,
    balance: 1200,
    auto_renew: false,
    vpn_profile_slug: 'universal',
    legal_consents: {
      version: '2026-03-01',
      privacy_policy_accepted: requiredConsentsAccepted,
      terms_of_use_accepted: requiredConsentsAccepted,
      personal_data_consent_accepted: requiredConsentsAccepted,
      marketing_consent_granted: false,
      required_consents_accepted: requiredConsentsAccepted,
      accepted_at: {
        privacy_policy: requiredConsentsAccepted ? '2026-03-07T00:00:00Z' : null,
        terms_of_use: requiredConsentsAccepted ? '2026-03-07T00:00:00Z' : null,
        personal_data: requiredConsentsAccepted ? '2026-03-07T00:00:00Z' : null,
        marketing: null,
      },
    },
    subscriptions: {
      vpn: { active: true, trial_available: false },
      mtproto: { active: true, trial_available: false },
      whatsapp: { active: true, trial_available: false },
    },
    features: {
      mtproto_enabled: true,
      whatsapp_enabled: true,
      stars_enabled: true,
    },
  };
}

const VPN_PROFILES: VpnProfileOption[] = [
  { slug: 'universal', name: 'Универсальный', name_en: 'Universal', emoji: '🌐', kind: 'universal', order: 1 },
  { slug: 'mts', name: 'МТС', name_en: 'MTS', emoji: '📶', kind: 'operator', order: 2 },
  { slug: 'beeline', name: 'Билайн', name_en: 'Beeline', emoji: '📡', kind: 'operator', order: 3 },
];

function createDefaultVpnSubscriptions(): VpnSubscription[] {
  return [
    {
      subscription_id: 101,
      active: true,
      key: 'vless://vpn-subscription-101',
      location: 'Amsterdam',
      expiry_time: 1798713600000,
      traffic_up: 1024,
      traffic_down: 2048,
      traffic_used: 3072,
      max_devices: 2,
      current_profile: VPN_PROFILES[0],
      available_profiles: VPN_PROFILES,
      cancelled_at: null,
    },
  ];
}

function createDefaultMtprotoSubscriptions(): MtprotoSubscription[] {
  return [
    {
      subscription_id: 201,
      active: true,
      expires_at: '2026-12-31T00:00:00Z',
      link: 'tg://proxy?server=test&port=443&secret=abcdef',
      location: 'Amsterdam',
      cancelled_at: null,
    },
  ];
}

function createDefaultWhatsappSubscriptions(): WhatsappSubscription[] {
  return [
    {
      subscription_id: 301,
      active: true,
      expires_at: '2026-12-31T00:00:00Z',
      host: 'proxy.proxycraft.tech',
      port: 10378,
      location: 'Amsterdam',
      cancelled_at: null,
    },
  ];
}

async function fulfillJson(route: Route, body: unknown, delay = 0, status = 200) {
  if (delay > 0) {
    await new Promise((resolve) => setTimeout(resolve, delay));
  }

  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

export async function mockApi(page: Page, options: MockApiOptions = {}) {
  const state = {
    me: structuredClone(options.me ?? createDefaultMe(true)),
    vpnSubscriptions: structuredClone(options.vpnSubscriptions ?? createDefaultVpnSubscriptions()),
    mtprotoSubscriptions: structuredClone(options.mtprotoSubscriptions ?? createDefaultMtprotoSubscriptions()),
    whatsappSubscriptions: structuredClone(options.whatsappSubscriptions ?? createDefaultWhatsappSubscriptions()),
  };
  const delays = options.delays ?? {};

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === 'POST' && path === '/api/v1/legal-consents') {
      const payload = JSON.parse(request.postData() ?? '{}') as {
        privacy_policy: boolean;
        terms_of_use: boolean;
        personal_data: boolean;
        marketing: boolean;
      };

      state.me.legal_consents = {
        ...state.me.legal_consents,
        privacy_policy_accepted: payload.privacy_policy,
        terms_of_use_accepted: payload.terms_of_use,
        personal_data_consent_accepted: payload.personal_data,
        marketing_consent_granted: payload.marketing,
        required_consents_accepted: payload.privacy_policy && payload.terms_of_use && payload.personal_data,
        accepted_at: {
          privacy_policy: payload.privacy_policy ? '2026-03-07T00:00:00Z' : null,
          terms_of_use: payload.terms_of_use ? '2026-03-07T00:00:00Z' : null,
          personal_data: payload.personal_data ? '2026-03-07T00:00:00Z' : null,
          marketing: payload.marketing ? '2026-03-07T00:00:00Z' : null,
        },
      };

      return fulfillJson(route, { legal_consents: state.me.legal_consents }, delays.acceptConsents);
    }

    if (request.method() === 'POST' && path === '/api/v1/subscription/vpn-profile') {
      const payload = JSON.parse(request.postData() ?? '{}') as {
        profile_slug: string;
        subscription_id?: number | null;
      };
      const targetId = payload.subscription_id ?? state.vpnSubscriptions[0]?.subscription_id;
      const selectedProfile = VPN_PROFILES.find((profile) => profile.slug === payload.profile_slug) ?? VPN_PROFILES[0];
      const targetIndex = state.vpnSubscriptions.findIndex((subscription) => subscription.subscription_id === targetId);

      if (targetIndex >= 0) {
        state.vpnSubscriptions[targetIndex] = {
          ...state.vpnSubscriptions[targetIndex],
          current_profile: selectedProfile,
        };
      }

      state.me.vpn_profile_slug = selectedProfile.slug;
      return fulfillJson(route, state.vpnSubscriptions[targetIndex], delays.changeVpnProfile);
    }

    switch (path) {
      case '/api/v1/me':
        return fulfillJson(route, state.me, delays.me);
      case '/api/v1/plans':
        return fulfillJson(route, { plans: [] });
      case '/api/v1/locations':
        return fulfillJson(route, {
          locations: [
            { name: 'Amsterdam', available: true },
            { name: 'Saint Petersburg', available: true },
          ],
        });
      case '/api/v1/subscription':
        return fulfillJson(route, state.vpnSubscriptions[0] ?? { active: false });
      case '/api/v1/subscriptions':
        return fulfillJson(route, {
          vpn: state.vpnSubscriptions,
          mtproto: state.mtprotoSubscriptions,
          whatsapp: state.whatsappSubscriptions,
        }, delays.subscriptions);
      case '/api/v1/subscriptions/vpn':
        return fulfillJson(route, { subscriptions: state.vpnSubscriptions }, delays.vpnSubscriptions);
      case '/api/v1/subscriptions/mtproto':
        return fulfillJson(route, { subscriptions: state.mtprotoSubscriptions }, delays.mtprotoSubscriptions);
      case '/api/v1/subscriptions/whatsapp':
        return fulfillJson(route, { subscriptions: state.whatsappSubscriptions }, delays.whatsappSubscriptions);
      case '/api/v1/subscription/mtproto':
        return fulfillJson(route, state.mtprotoSubscriptions[0] ?? { active: false });
      case '/api/v1/subscription/whatsapp':
        return fulfillJson(route, state.whatsappSubscriptions[0] ?? { active: false });
      default:
        return fulfillJson(route, {});
    }
  });
}
