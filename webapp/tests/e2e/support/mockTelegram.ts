import type { Page } from '@playwright/test';

export async function installTelegramMock(page: Page) {
  await page.addInitScript(() => {
    const WebApp = {
      initData: 'playwright-init-data',
      initDataUnsafe: {
        query_id: 'test-query',
        user: {
          id: 9990001,
          first_name: 'Playwright',
          username: 'playwright_user',
          language_code: 'en',
        },
      },
      version: '8.0',
      platform: 'android',
      colorScheme: 'dark',
      themeParams: {},
      isExpanded: true,
      viewportHeight: 844,
      viewportStableHeight: 844,
      ready() {},
      expand() {},
      close() {},
      sendData() {},
      setHeaderColor() {},
      setBackgroundColor() {},
      enableClosingConfirmation() {},
      disableClosingConfirmation() {},
      onEvent() {},
      offEvent() {},
      MainButton: {
        show() {},
        hide() {},
        setParams() {},
        onClick() {},
        offClick() {},
      },
      BackButton: {
        show() {},
        hide() {},
        onClick() {},
        offClick() {},
      },
      HapticFeedback: {
        impactOccurred() {},
        notificationOccurred() {},
        selectionChanged() {},
      },
      openLink(url: string) {
        window.open(url, '_blank', 'noopener,noreferrer');
      },
    };

    Object.defineProperty(window, 'Telegram', {
      configurable: true,
      value: { WebApp },
    });
  });
}
