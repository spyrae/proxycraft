import { createPortal } from 'react-dom';
import { useEffect, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

export type OverlayMode = 'hidden' | 'loading' | 'success';

interface StatusOverlayProps {
  mode: OverlayMode;
  loadingKey?: 'processing' | 'activating' | 'cancelling' | 'switching_profile';
  onDismiss?: () => void;
}

export function StatusOverlay({ mode, loadingKey = 'processing', onDismiss }: StatusOverlayProps) {
  const { t } = useLanguage();
  const [viewportCenterY, setViewportCenterY] = useState<number | null>(null);

  useEffect(() => {
    if (typeof document === 'undefined' || mode === 'hidden') return undefined;

    const { body } = document;
    const previousOverflow = body.style.overflow;
    body.style.overflow = 'hidden';

    return () => {
      body.style.overflow = previousOverflow;
    };
  }, [mode]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const syncViewportCenter = () => {
      const viewport = window.visualViewport;
      if (viewport) {
        setViewportCenterY(viewport.offsetTop + viewport.height / 2);
        return;
      }

      setViewportCenterY(window.innerHeight / 2);
    };

    syncViewportCenter();

    const viewport = window.visualViewport;
    viewport?.addEventListener('resize', syncViewportCenter);
    viewport?.addEventListener('scroll', syncViewportCenter);
    window.addEventListener('resize', syncViewportCenter);
    window.addEventListener('scroll', syncViewportCenter, { passive: true });

    return () => {
      viewport?.removeEventListener('resize', syncViewportCenter);
      viewport?.removeEventListener('scroll', syncViewportCenter);
      window.removeEventListener('resize', syncViewportCenter);
      window.removeEventListener('scroll', syncViewportCenter);
    };
  }, []);

  const contentTop = viewportCenterY ?? null;

  if (mode === 'hidden' || typeof document === 'undefined') return null;

  const overlay = (
    <div
      className="fixed inset-0"
      style={{ zIndex: 9000 }}
      aria-live="polite"
      aria-busy={mode === 'loading'}
    >
      <div
        className="absolute inset-0 animate-overlay-fade"
        style={{
          backgroundColor: 'rgba(3, 7, 18, 0.72)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
        }}
      />

      <div
        className="absolute left-1/2 w-[min(320px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 animate-fade-in-scale"
        style={{
          top: contentTop ?? '50%',
          backgroundColor: 'rgba(10, 16, 30, 0.96)',
          border: '1px solid rgba(52, 211, 153, 0.18)',
          boxShadow: '0 22px 80px rgba(0, 0, 0, 0.55)',
          borderRadius: '28px',
        }}
      >
        <div className="flex flex-col items-center gap-5 px-8 py-10 text-center">
          {mode === 'loading' ? (
            <>
              <BrandLoader />
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
    </div>
  );

  return createPortal(overlay, document.body);
}

function AnimatedText({ text }: { text: string }) {
  const [phase, setPhase] = useState(0);
  const normalizedText = text.replace(/\.+$/u, '');

  useEffect(() => {
    const id = setInterval(() => setPhase((p) => (p + 1) % 4), 500);
    return () => clearInterval(id);
  }, []);

  return (
    <p className="text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
      {normalizedText}
      {'...'.slice(0, phase)}
    </p>
  );
}

function BrandLoader() {
  return (
    <div className="relative h-[88px] w-[88px]">
      <svg
        className="absolute inset-0 h-full w-full animate-spin"
        viewBox="0 0 88 88"
        fill="none"
        aria-hidden="true"
      >
        <circle cx="44" cy="44" r="34" stroke="rgba(16,185,129,0.16)" strokeWidth="6" />
        <path
          d="M44 10a34 34 0 0 1 31.4 20.9"
          stroke="#34D399"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d="M73.6 30.9A34 34 0 0 1 62.2 72.5"
          stroke="#10B981"
          strokeWidth="6"
          strokeLinecap="round"
        />
      </svg>
      <div
        className="absolute inset-[14px] flex items-center justify-center rounded-full"
        style={{
          background: 'radial-gradient(circle at top, rgba(16,185,129,0.2), rgba(10,16,30,0.98) 70%)',
          border: '1px solid rgba(52, 211, 153, 0.18)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
        }}
      >
        <img
          src="/favicon.svg?v=2"
          alt="ProxyCraft"
          className="h-10 w-10 rounded-xl object-contain"
        />
      </div>
    </div>
  );
}
