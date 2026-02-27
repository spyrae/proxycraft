import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  init,
  restoreInitData,
  bindThemeParamsCssVars,
  bindMiniAppCssVars,
  mountMiniApp,
  miniAppReady,
  setMiniAppHeaderColor,
  mountThemeParams,
} from '@telegram-apps/sdk-react';
import './styles/globals.css';
import App from './App';

// Initialize Telegram Mini App SDK
try {
  init();
  mountMiniApp();
  mountThemeParams();
  restoreInitData();
  bindThemeParamsCssVars();
  bindMiniAppCssVars();
  miniAppReady();
  setMiniAppHeaderColor('secondary_bg_color');
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
