import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  init,
  restoreInitData,
  bindMiniAppCssVars,
  mountMiniApp,
  miniAppReady,
  setMiniAppHeaderColor,
  mountThemeParams,
} from '@telegram-apps/sdk-react';
import './styles/globals.css';
import App from './App';
import { api } from './api/client';

// Initialize Telegram Mini App SDK
try {
  init();
  mountMiniApp();
  mountThemeParams();
  restoreInitData();
  bindMiniAppCssVars();
  miniAppReady();
  setMiniAppHeaderColor('#0A0E17' as Parameters<typeof setMiniAppHeaderColor>[0]);
} catch (e) {
  console.warn('TMA SDK init failed (outside Telegram?):', e);
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Prefetch only the shell-critical profile immediately. Heavier tab data is warmed up
// after the first paint to keep Mini App startup responsive.
queryClient.prefetchQuery({
  queryKey: ['me'],
  queryFn: () => api('/api/v1/me'),
  staleTime: 5 * 60_000,
});

const scheduleIdleWarmup = (
  callback: () => void,
) => {
  if (typeof window === 'undefined') {
    return;
  }

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(() => callback());
    return;
  }

  globalThis.setTimeout(callback, 250);
};

scheduleIdleWarmup(() => {
  queryClient.prefetchQuery({
    queryKey: ['plans'],
    queryFn: () => api('/api/v1/plans'),
    staleTime: 5 * 60_000,
  });
  queryClient.prefetchQuery({
    queryKey: ['locations'],
    queryFn: () => api('/api/v1/locations'),
    staleTime: 5 * 60_000,
  });
  queryClient.prefetchQuery({
    queryKey: ['subscriptions'],
    queryFn: () => api('/api/v1/subscriptions'),
    staleTime: 60_000,
  });
});

// Hide splash when React mounts (data prefetch already started)
function hideSplash() {
  const splash = document.getElementById('splash');
  if (splash) {
    splash.classList.add('hidden');
    setTimeout(() => splash.remove(), 400);
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App onReady={hideSplash} />
    </QueryClientProvider>
  </StrictMode>,
);
