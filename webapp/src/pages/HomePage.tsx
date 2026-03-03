import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { openInvoice } from '@telegram-apps/sdk-react';
import { openLink } from '@telegram-apps/sdk';
import { useTelegram } from '../hooks/useTelegram';
import { useMe, useVpnSubscription, useTopup, useAutoRenew } from '../api/hooks';

const STARS_RATE = 1.8;
const TOPUP_AMOUNTS = [250, 500, 1000, 2000];

export function HomePage() {
  const { user } = useTelegram();
  const { data: me, isLoading, error } = useMe();

  if (isLoading) return <HomeLoading />;
  if (error || !me) return <HomeError />;

  const hasActiveVpn = me.subscriptions.vpn.active;

  return (
    <div className="animate-fade-in">
      {/* Greeting */}
      <p className="text-sm font-medium mb-4" style={{ color: 'var(--text-muted)' }}>
        Hi, {user?.first_name || me.first_name}
      </p>

      {/* Balance Card */}
      <BalanceCard balance={me.balance} autoRenew={me.auto_renew} />

      {/* Hero Shield */}
      <HeroSection active={hasActiveVpn} />

      {/* Stats or Quick Setup */}
      {hasActiveVpn ? <ActiveStats /> : <QuickSetup me={me} />}
    </div>
  );
}

function BalanceCard({ balance, autoRenew }: { balance: number; autoRenew: boolean }) {
  const [showTopup, setShowTopup] = useState(false);
  const autoRenewMutation = useAutoRenew();

  const handleToggleAutoRenew = () => {
    autoRenewMutation.mutate({ enabled: !autoRenew });
  };

  return (
    <>
      <div className="card-gradient-border p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
              Balance
            </span>
            <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              {balance.toFixed(0)} ₽
            </span>
          </div>
          <button
            onClick={() => setShowTopup(true)}
            className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-bold transition-all"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#10B981',
            }}
          >
            +
          </button>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
            Auto-renewal
          </span>
          <button
            onClick={handleToggleAutoRenew}
            disabled={autoRenewMutation.isPending}
            className="relative w-10 h-5 rounded-full transition-all duration-200"
            style={{
              backgroundColor: autoRenew ? '#10B981' : 'var(--border)',
              opacity: autoRenewMutation.isPending ? 0.5 : 1,
            }}
          >
            <span
              className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-200"
              style={{
                left: autoRenew ? '22px' : '2px',
              }}
            />
          </button>
        </div>
      </div>

      {showTopup && <TopupModal onClose={() => setShowTopup(false)} />}
    </>
  );
}

function TopupModal({ onClose }: { onClose: () => void }) {
  const [selectedAmount, setSelectedAmount] = useState<number>(500);
  const [currency, setCurrency] = useState<'stars' | 'rub'>('stars');
  const topupMutation = useTopup();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'redirected' | 'error'>('idle');
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const starsAmount = Math.max(1, Math.round(selectedAmount / STARS_RATE));

  // Cleanup timer on unmount
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
        // T-Bank: payment happens externally, we can't confirm it here
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

        {/* Currency toggle */}
        <div
          className="flex rounded-xl p-1 mb-4"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <button
            onClick={() => setCurrency('stars')}
            className="flex-1 text-sm font-semibold py-2 rounded-lg transition-all"
            style={{
              backgroundColor: currency === 'stars' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: currency === 'stars' ? '#10B981' : 'var(--text-dim)',
            }}
          >
            ★ Stars
          </button>
          <button
            onClick={() => setCurrency('rub')}
            className="flex-1 text-sm font-semibold py-2 rounded-lg transition-all"
            style={{
              backgroundColor: currency === 'rub' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: currency === 'rub' ? '#10B981' : 'var(--text-dim)',
            }}
          >
            💳 Card
          </button>
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

function HeroSection({ active }: { active: boolean }) {
  return (
    <div className="flex flex-col items-center mb-6">
      {/* Shield icon with glow */}
      <div
        className="relative w-24 h-24 flex items-center justify-center mb-4"
        style={{
          filter: active
            ? 'drop-shadow(0 0 20px rgba(16, 185, 129, 0.5))'
            : 'drop-shadow(0 0 10px rgba(107, 114, 128, 0.3))',
        }}
      >
        {active && (
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(16, 185, 129, 0.15) 0%, transparent 70%)',
              animation: 'glow-pulse 3s ease-in-out infinite',
            }}
          />
        )}
        <img
          src="/favicon.svg?v=2"
          width="64"
          height="64"
          alt="ProxyCraft"
          style={{
            opacity: active ? 1 : 0.45,
            transition: 'opacity 0.3s ease',
          }}
        />
      </div>

      {/* Status text */}
      <h1
        className="text-xl font-bold mb-1"
        style={{ color: active ? '#10B981' : '#9CA3AF' }}
      >
        {active ? 'Protected' : 'Not Protected'}
      </h1>
      <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
        {active ? 'Your connection is secure' : 'Get a plan to stay safe online'}
      </p>
    </div>
  );
}

function ActiveStats() {
  const { data: sub, isLoading } = useVpnSubscription();

  if (isLoading || !sub) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="animate-shimmer rounded-2xl h-20" />
        ))}
      </div>
    );
  }

  const daysLeft = sub.expiry_time
    ? Math.max(0, Math.ceil((sub.expiry_time - Date.now()) / (1000 * 60 * 60 * 24)))
    : 0;

  // Progress based on typical 30-day subscription
  const progressPercent = sub.expiry_time
    ? Math.min(100, Math.max(0, (daysLeft / 30) * 100))
    : 0;

  return (
    <div className="space-y-3 animate-slide-up">
      {/* Subscription progress */}
      {sub.expiry_time && sub.expiry_time > 0 && (
        <div className="card-gradient-border p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Subscription
            </span>
            <span
              className="text-xs font-bold"
              style={{ color: daysLeft <= 3 ? 'var(--danger)' : '#10B981' }}
            >
              {daysLeft} days left
            </span>
          </div>
          <div
            className="w-full h-1.5 rounded-full overflow-hidden"
            style={{ backgroundColor: 'var(--border)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progressPercent}%`,
                background: daysLeft <= 3
                  ? 'linear-gradient(90deg, #EF4444, #F59E0B)'
                  : 'linear-gradient(90deg, #10B981, #34D399)',
              }}
            />
          </div>
          <p className="text-[10px] mt-1.5" style={{ color: 'var(--text-dim)' }}>
            Expires {new Date(sub.expiry_time).toLocaleDateString()}
          </p>
        </div>
      )}

      {/* Traffic stats grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          icon="↑"
          label="Upload"
          value={formatBytes(sub.traffic_up || 0)}
          color="#06B6D4"
        />
        <StatCard
          icon="↓"
          label="Download"
          value={formatBytes(sub.traffic_down || 0)}
          color="#10B981"
        />
        <StatCard
          icon="◎"
          label="Total Used"
          value={formatBytes(sub.traffic_used || 0)}
          color="#8B5CF6"
        />
        <StatCard
          icon="⊞"
          label="Devices"
          value={sub.max_devices === -1 ? '∞' : String(sub.max_devices || 0)}
          color="#F59E0B"
        />
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: string;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="card-gradient-border p-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span
          className="w-5 h-5 rounded-md flex items-center justify-center text-[10px]"
          style={{ backgroundColor: `${color}20`, color }}
        >
          {icon}
        </span>
        <span className="text-[10px] font-medium" style={{ color: 'var(--text-dim)' }}>
          {label}
        </span>
      </div>
      <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
        {value}
      </p>
    </div>
  );
}

interface MeData {
  subscriptions: {
    vpn: { active: boolean; trial_available: boolean };
    mtproto: { active: boolean; trial_available: boolean };
    whatsapp: { active: boolean; trial_available: boolean };
  };
  features: {
    mtproto_enabled: boolean;
    whatsapp_enabled: boolean;
    stars_enabled: boolean;
  };
  first_name: string;
}

function QuickSetup({ me }: { me: MeData }) {
  const navigate = useNavigate();

  const steps = [
    {
      num: '1',
      title: 'Top up balance',
      desc: 'Add funds via Stars or card',
      action: undefined as (() => void) | undefined,
      color: '#F59E0B',
    },
    {
      num: '2',
      title: 'Choose a Plan',
      desc: 'Select the plan that fits your needs',
      action: () => navigate('/plans'),
      color: '#10B981',
    },
    {
      num: '3',
      title: 'Connect',
      desc: 'Scan QR or copy the config link',
      color: '#8B5CF6',
    },
  ];

  return (
    <div className="space-y-3 animate-slide-up">
      <h2 className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>
        Get Started
      </h2>

      {steps.map((step, i) => (
        <button
          key={i}
          onClick={step.action}
          disabled={!step.action}
          className="w-full card-gradient-border p-4 text-left flex items-center gap-3 transition-all"
          style={{ opacity: step.action ? 1 : 0.6 }}
        >
          <span
            className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-bold shrink-0"
            style={{ backgroundColor: `${step.color}20`, color: step.color }}
          >
            {step.num}
          </span>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {step.title}
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
              {step.desc}
            </p>
          </div>
          {step.action && (
            <svg
              className="ml-auto shrink-0"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke={step.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
          )}
        </button>
      ))}

      {me.subscriptions.vpn.trial_available && (
        <div
          className="card-gradient-border p-4 text-center"
          style={{ borderColor: 'rgba(16, 185, 129, 0.3)' }}
        >
          <p className="text-sm font-semibold" style={{ color: '#10B981' }}>
            Free 7-day trial available!
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
            No payment required to start
          </p>
        </div>
      )}
    </div>
  );
}

function HomeLoading() {
  return (
    <div className="space-y-4">
      <div className="animate-shimmer rounded-xl h-6 w-32" />
      <div className="animate-shimmer rounded-2xl h-20" />
      <div className="flex flex-col items-center gap-4 my-8">
        <div className="animate-shimmer rounded-full w-24 h-24" />
        <div className="animate-shimmer rounded-xl h-6 w-36" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="animate-shimmer rounded-2xl h-20" />
        ))}
      </div>
    </div>
  );
}

function HomeError() {
  return (
    <div className="flex flex-col items-center justify-center h-60 gap-3 animate-fade-in">
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center"
        style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      </div>
      <p className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
        Failed to load profile
      </p>
      <button
        onClick={() => window.location.reload()}
        className="text-sm font-semibold px-5 py-2.5 rounded-xl transition-all"
        style={{
          backgroundColor: '#10B981',
          color: '#ffffff',
        }}
      >
        Retry
      </button>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(value < 10 ? 2 : 1)} ${units[i]}`;
}
