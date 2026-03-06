import { useState, useCallback, useEffect, useRef } from 'react';
import { openInvoice } from '@telegram-apps/sdk-react';
import { openLink } from '@telegram-apps/sdk';
import { useTopup } from '../api/hooks';

const STARS_RATE = 1.8;
const TOPUP_AMOUNTS = [250, 500, 1000, 2000];

export function TopupModal({ onClose }: { onClose: () => void }) {
  const [selectedAmount, setSelectedAmount] = useState<number>(500);
  const [currency, setCurrency] = useState<'stars' | 'rub' | 'sbp'>('stars');
  const topupMutation = useTopup();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'redirected' | 'error'>('idle');
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const starsAmount = Math.max(1, Math.round(selectedAmount / STARS_RATE));

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
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

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-md rounded-t-3xl p-6 animate-slide-up"
        style={{ backgroundColor: 'var(--bg-primary)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
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

        {/* Amount selection */}
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

        {/* Payment method toggle */}
        <div
          className="flex rounded-xl p-1 mb-4"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          {([
            { key: 'stars' as const, label: '★ Stars' },
            { key: 'sbp' as const, label: '⚡ СБП' },
            { key: 'rub' as const, label: '💳 Card' },
          ]).map((opt) => (
            <button
              key={opt.key}
              onClick={() => setCurrency(opt.key)}
              className="flex-1 text-xs font-semibold py-2 rounded-lg transition-all"
              style={{
                backgroundColor: currency === opt.key ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                color: currency === opt.key ? '#10B981' : 'var(--text-dim)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Conversion info for Stars */}
        {currency === 'stars' && (
          <p className="text-xs text-center mb-4" style={{ color: 'var(--text-dim)' }}>
            {selectedAmount}₽ = {starsAmount} ★
          </p>
        )}

        {/* Submit button */}
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
  );
}
