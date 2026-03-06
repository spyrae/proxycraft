import { useEffect, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

export type OverlayMode = 'hidden' | 'loading' | 'success';

interface StatusOverlayProps {
  mode: OverlayMode;
  loadingKey?: 'processing' | 'activating' | 'cancelling';
  onDismiss?: () => void;
}

export function StatusOverlay({ mode, loadingKey = 'processing', onDismiss }: StatusOverlayProps) {
  const { t } = useLanguage();

  if (mode === 'hidden') return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="flex flex-col items-center gap-5 px-8 py-10 rounded-3xl mx-4"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border)',
          minWidth: '220px',
        }}
      >
        {mode === 'loading' ? (
          <>
            <div className="relative w-16 h-16">
              <svg className="animate-spin w-16 h-16" viewBox="0 0 64 64" fill="none">
                <circle cx="32" cy="32" r="28" stroke="rgba(16,185,129,0.15)" strokeWidth="4" />
                <path
                  d="M32 4a28 28 0 0 1 28 28"
                  stroke="#10B981"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center text-2xl select-none">
                ⚒️
              </div>
            </div>
            <AnimatedText text={t(loadingKey)} />
          </>
        ) : (
          <>
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center"
              style={{
                backgroundColor: 'rgba(16,185,129,0.12)',
                border: '2px solid rgba(16,185,129,0.3)',
              }}
            >
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <path
                  d="M6 16l7 7 13-13"
                  stroke="#10B981"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <div className="text-center space-y-1">
              <p className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                {t('sub_activated')}
              </p>
              <p className="text-sm" style={{ color: 'var(--text-dim)' }}>
                {t('plan_now_active')}
              </p>
            </div>

            <button
              onClick={onDismiss}
              className="w-full rounded-2xl py-3 text-sm font-bold transition-all"
              style={{
                backgroundColor: '#10B981',
                color: '#ffffff',
                boxShadow: '0 4px 15px rgba(16,185,129,0.3)',
              }}
            >
              {t('dismiss')}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function AnimatedText({ text }: { text: string }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setPhase((p) => (p + 1) % 4), 500);
    return () => clearInterval(id);
  }, []);

  return (
    <p className="text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
      {text}
      {'...'.slice(0, phase)}
    </p>
  );
}
