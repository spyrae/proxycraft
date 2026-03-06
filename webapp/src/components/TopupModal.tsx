import { useState, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { openInvoice } from '@telegram-apps/sdk-react';
import { openLink } from '@telegram-apps/sdk';
import { useTopup } from '../api/hooks';

const STARS_RATE = 1.8;
const TOPUP_AMOUNTS = [250, 500, 1000, 2000];

function StarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function LightningIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function CardIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  );
}

const PAYMENT_METHODS = [
  { key: 'stars' as const, label: 'Stars', Icon: StarIcon },
  { key: 'sbp' as const, label: 'СБП', Icon: LightningIcon },
  { key: 'rub' as const, label: 'Card', Icon: CardIcon },
];

export function TopupModal({ onClose }: { onClose: () => void }) {
  const [selectedAmount, setSelectedAmount] = useState<number>(500);
  const [currency, setCurrency] = useState<'stars' | 'rub' | 'sbp'>('stars');
  const topupMutation = useTopup();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'redirected' | 'error'>('idle');
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const starsAmount = Math.max(1, Math.round(selectedAmount / STARS_RATE));

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const handleTopup = useCallback(async () => {
    setStatus('loading');
    try {
      const response = await topupMutation.mutateAsync({
        amount: selectedAmount,
        currency,
      });

      if (response.invoice_url) {
        const result = await openInvoice(response.invoice_url, 'url');
        if (result === 'paid') {
          setStatus('success');
          closeTimerRef.current = setTimeout(onClose, 1500);
        } else {
          setStatus('idle');
        }
      } else if (response.payment_url) {
        openLink(response.payment_url, { tryBrowser: 'chrome' });
        setStatus('redirected');
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
    }
  }, [selectedAmount, currency, topupMutation, onClose]);

  if (typeof document === 'undefined') {
    return null;
  }

  return createPortal(
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 9000,
          background: 'rgba(0, 0, 0, 0.5)',
          animation: 'overlay-fade 0.2s ease-out forwards',
        }}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="topup-modal-title"
        className="rounded-t-3xl"
        onClick={(event) => event.stopPropagation()}
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          width: '100vw',
          maxWidth: '100vw',
          zIndex: 9001,
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '24px 24px 0 0',
          animation: 'sheet-up 0.3s ease-out forwards',
          boxShadow: '0 -20px 50px rgba(0, 0, 0, 0.45)',
        }}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div
            className="w-10 h-1 rounded-full"
            style={{ backgroundColor: 'var(--border)' }}
          />
        </div>

        <div
          className="px-6 pt-3"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2rem)' }}
        >
          <div className="flex items-center justify-between mb-5">
            <h2
              id="topup-modal-title"
              className="text-lg font-bold"
              style={{ color: 'var(--text-primary)' }}
            >
              Top up balance
            </h2>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-dim)' }}
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-4 gap-2 mb-4">
            {TOPUP_AMOUNTS.map((amount) => (
              <button
                key={amount}
                onClick={() => setSelectedAmount(amount)}
                className="py-2.5 rounded-xl text-sm font-semibold transition-all"
                style={{
                  backgroundColor:
                    selectedAmount === amount ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-card)',
                  color: selectedAmount === amount ? '#10B981' : 'var(--text-muted)',
                  border: `1px solid ${
                    selectedAmount === amount ? 'rgba(16, 185, 129, 0.3)' : 'var(--border)'
                  }`,
                }}
              >
                {amount}₽
              </button>
            ))}
          </div>

          <div
            className="flex rounded-xl p-1 mb-4"
            style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            {PAYMENT_METHODS.map(({ key, label, Icon }) => {
              const active = currency === key;
              return (
                <button
                  key={key}
                  onClick={() => setCurrency(key)}
                  className="flex-1 flex flex-col items-center gap-1 py-2 rounded-lg transition-all"
                  style={{
                    backgroundColor: active ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                    color: active ? '#10B981' : 'var(--text-dim)',
                  }}
                >
                  <Icon />
                  <span className="text-[10px] font-semibold">{label}</span>
                </button>
              );
            })}
          </div>

          {currency === 'stars' && (
            <p className="text-xs text-center mb-4" style={{ color: 'var(--text-dim)' }}>
              {selectedAmount}₽ = {starsAmount} ★
            </p>
          )}

          <button
            onClick={status === 'redirected' ? onClose : handleTopup}
            disabled={status === 'loading'}
            className="w-full rounded-2xl p-4 text-center text-sm font-bold transition-all"
            style={{
              backgroundColor: status === 'loading' ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
              color: '#ffffff',
              boxShadow: status === 'loading' ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
            }}
          >
            {status === 'loading'
              ? 'Processing...'
              : status === 'success'
                ? 'Success!'
                : status === 'redirected'
                  ? 'Done'
                  : `Top up ${selectedAmount}₽`}
          </button>

          {status === 'redirected' && (
            <p className="text-xs text-center mt-2" style={{ color: 'var(--text-dim)' }}>
              Complete the payment in the opened page. Balance will update automatically.
            </p>
          )}

          {status === 'error' && (
            <p className="text-xs text-center mt-2" style={{ color: 'var(--danger, #EF4444)' }}>
              Failed to create payment. Try again.
            </p>
          )}
        </div>
      </div>
    </>,
    document.body,
  );
}
