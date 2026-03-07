import { expect, test } from '@playwright/test';
import type { UserProfile, VpnSubscription } from '../../src/api/types';
import { mockApi } from './support/mockApi';
import { installTelegramMock } from './support/mockTelegram';

test.beforeEach(async ({ page }) => {
  await installTelegramMock(page);
});

test('shows loaded subscriptions while keeping skeletons for slower sections', async ({ page }) => {
  await mockApi(page, {
    delays: {
      mtprotoSubscriptions: 1200,
      whatsappSubscriptions: 1200,
    },
  });

  await page.goto('/my-vpn');

  await expect(page.getByRole('heading', { name: 'My VPN' })).toBeVisible();
  await expect(page.getByText(/^VPN$/).first()).toBeVisible();
  await expect(page.getByTestId('subscription-skeleton')).toHaveCount(2);

  await expect(page.getByText(/^Telegram Proxy$/).first()).toBeVisible({ timeout: 3000 });
  await expect(page.getByText(/^WhatsApp Proxy$/).first()).toBeVisible({ timeout: 3000 });
  await expect(page.getByTestId('subscription-skeleton')).toHaveCount(0);
});

test('switches VPN profile and shows fullscreen overlay during the request', async ({ page }) => {
  const me: UserProfile = {
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
      privacy_policy_accepted: true,
      terms_of_use_accepted: true,
      personal_data_consent_accepted: true,
      marketing_consent_granted: false,
      required_consents_accepted: true,
      accepted_at: {
        privacy_policy: '2026-03-07T00:00:00Z',
        terms_of_use: '2026-03-07T00:00:00Z',
        personal_data: '2026-03-07T00:00:00Z',
        marketing: null,
      },
    },
    subscriptions: {
      vpn: { active: true, trial_available: false },
      mtproto: { active: false, trial_available: false },
      whatsapp: { active: false, trial_available: false },
    },
    features: {
      mtproto_enabled: false,
      whatsapp_enabled: false,
      stars_enabled: true,
    },
  };

  const vpnSubscriptions: VpnSubscription[] = [
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
      current_profile: {
        slug: 'universal',
        name: 'Универсальный',
        name_en: 'Universal',
        emoji: '🌐',
        kind: 'universal',
        order: 1,
      },
      available_profiles: [
        {
          slug: 'universal',
          name: 'Универсальный',
          name_en: 'Universal',
          emoji: '🌐',
          kind: 'universal',
          order: 1,
        },
        {
          slug: 'mts',
          name: 'МТС',
          name_en: 'MTS',
          emoji: '📶',
          kind: 'operator',
          order: 2,
        },
      ],
      cancelled_at: null,
    },
  ];

  await mockApi(page, {
    me,
    vpnSubscriptions,
    mtprotoSubscriptions: [],
    whatsappSubscriptions: [],
    delays: {
      changeVpnProfile: 900,
    },
  });

  await page.goto('/my-vpn');
  await page.getByRole('button', { name: 'Details' }).click();

  const universalButton = page.getByRole('button', { name: /Universal/i });
  const mtsButton = page.getByRole('button', { name: /MTS/i });

  await expect(universalButton).toHaveAttribute('aria-pressed', 'true');
  await mtsButton.click();

  await expect(page.getByText('Applying settings')).toBeVisible();
  await expect(mtsButton).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
  await expect(universalButton).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByText('Applying settings')).toHaveCount(0);
});
