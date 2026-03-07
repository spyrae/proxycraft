import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LegalConsentGate } from './components/LegalConsentGate';
import { HomePage } from './pages/HomePage';
import { PlansPage } from './pages/PlansPage';
import { MyVpnPage } from './pages/MyVpnPage';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';
import { useMe } from './api/hooks';

export default function App({ onReady }: { onReady?: () => void }) {
  return (
    <LanguageProvider>
      <AppShell onReady={onReady} />
    </LanguageProvider>
  );
}

function AppShell({ onReady }: { onReady?: () => void }) {
  const { data: me, isLoading, error, refetch } = useMe();
  const { t } = useLanguage();

  useEffect(() => {
    onReady?.();
  }, [onReady]);

  if (isLoading && !me) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center px-6">
        <div className="w-full max-w-sm rounded-[28px] p-6 animate-fade-in-scale" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="animate-shimmer rounded-2xl h-12 mb-4" />
          <div className="animate-shimmer rounded-2xl h-24" />
        </div>
      </div>
    );
  }

  if (error && !me) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center px-6">
        <div className="w-full max-w-sm rounded-[28px] p-6 animate-fade-in-scale" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            {t('consent_error_title')}
          </h1>
          <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
            {t('consent_error_body')}
          </p>
          <button
            onClick={() => void refetch()}
            className="min-h-11 px-4 rounded-2xl text-sm font-semibold"
            style={{ background: 'linear-gradient(90deg, #10B981, #34D399)', color: '#03130D' }}
          >
            {t('retry')}
          </button>
        </div>
      </div>
    );
  }

  if (me && !me.legal_consents.required_consents_accepted) {
    return <LegalConsentGate />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/plans" element={<PlansPage />} />
          <Route path="/my-vpn" element={<MyVpnPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
