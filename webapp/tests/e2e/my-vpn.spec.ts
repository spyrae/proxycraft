import { expect, test } from '@playwright/test';
import type { VpnSubscription } from '../../src/api/types';
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
    vpnSubscriptions,
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
