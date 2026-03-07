import { expect, test } from '@playwright/test';
import type { UserProfile } from '../../src/api/types';
import { installTelegramMock } from './support/mockTelegram';
import { mockApi } from './support/mockApi';

test.beforeEach(async ({ page }) => {
  await installTelegramMock(page);
});

test('shows compact legal consent gate and requires the three mandatory consents', async ({ page }) => {
  const me: UserProfile = {
    tg_id: 9990001,
    first_name: 'Playwright',
    username: 'playwright_user',
    created_at: '2026-03-07T00:00:00Z',
    is_admin: false,
    balance: 1200,
    auto_renew: false,
    vpn_profile_slug: null,
    legal_consents: {
      version: '2026-03-01',
      privacy_policy_accepted: false,
      terms_of_use_accepted: false,
      personal_data_consent_accepted: false,
      marketing_consent_granted: false,
      required_consents_accepted: false,
      accepted_at: {
        privacy_policy: null,
        terms_of_use: null,
        personal_data: null,
        marketing: null,
      },
    },
    subscriptions: {
      vpn: { active: false, trial_available: false },
      mtproto: { active: false, trial_available: false },
      whatsapp: { active: false, trial_available: false },
    },
    features: {
      mtproto_enabled: true,
      whatsapp_enabled: true,
      stars_enabled: true,
    },
  };

  await mockApi(page, {
    me,
    vpnSubscriptions: [],
    mtprotoSubscriptions: [],
    whatsappSubscriptions: [],
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Before you continue' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open' })).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Enter' })).toBeDisabled();

  await page.getByRole('button', { name: 'I accept the Privacy Policy' }).click();
  await page.getByRole('button', { name: 'I accept the Terms of Use' }).click();
  await page.getByRole('button', { name: 'I consent to the processing of personal data' }).click();

  await expect(page.getByRole('button', { name: 'Enter' })).toBeEnabled();
});
