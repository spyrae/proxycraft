import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useMe,
  usePlans,
  useMtprotoPlans,
  useWhatsappPlans,
  useTrialVpn,
  useTrialMtproto,
  useTrialWhatsapp,
  useActivatePromocode,
  useBuyPlan,
} from '../api/hooks';
import { ApiRequestError } from '../api/client';
import { PlanCard } from '../components/PlanCard';

type Tab = 'vpn' | 'mtproto' | 'whatsapp';

export function PlansPage() {
  const { data: me } = useMe();
  const [tab, setTab] = useState<Tab>('vpn');

  const tabs: { key: Tab; label: string }[] = useMemo(() => {
    const t: { key: Tab; label: string }[] = [{ key: 'vpn', label: 'VPN' }];
    if (me?.features.mtproto_enabled) t.push({ key: 'mtproto', label: 'MTProto' });
    if (me?.features.whatsapp_enabled) t.push({ key: 'whatsapp', label: 'WhatsApp' });
    return t;
  }, [me]);

  return (
    <div className="animate-fade-in">
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        Plans
      </h1>

      {/* Balance info */}
      {me && (
        <BalanceBanner balance={me.balance} />
      )}

      {/* Segment control */}
      {tabs.length > 1 && (
        <div
          className="flex rounded-xl p-1 mb-4"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex-1 text-sm font-semibold py-2 rounded-lg transition-all duration-200"
              style={{
                backgroundColor: tab === t.key ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                color: tab === t.key ? '#10B981' : 'var(--text-dim)',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {tab === 'vpn' && <VpnPlans />}
      {tab === 'mtproto' && <ServicePlans product="mtproto" />}
      {tab === 'whatsapp' && <ServicePlans product="whatsapp" />}
    </div>
  );
}

function BalanceBanner({ balance }: { balance: number }) {
  const navigate = useNavigate();

  return (
    <div
      className="flex items-center justify-between rounded-2xl p-3 mb-4"
      style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
          Balance:
        </span>
        <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
          {balance.toFixed(0)} ₽
        </span>
      </div>
      <button
        onClick={() => navigate('/')}
        className="text-xs font-semibold px-3 py-1 rounded-lg"
        style={{ color: '#10B981' }}
      >
        Top up
      </button>
    </div>
  );
}

function PurchaseSuccessBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div
      className="rounded-2xl p-4 mb-4 text-center"
      style={{
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        border: '1px solid rgba(16, 185, 129, 0.3)',
      }}
    >
      <p className="text-sm font-semibold mb-1" style={{ color: '#10B981' }}>
        Subscription activated!
      </p>
      <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
        Your plan is now active
      </p>
      <button
        onClick={onDismiss}
        className="text-xs font-medium px-3 py-1 rounded-lg"
        style={{ color: 'var(--text-dim)' }}
      >
        Dismiss
      </button>
    </div>
  );
}

function InsufficientBalanceBanner() {
  const navigate = useNavigate();

  return (
    <div
      className="rounded-2xl p-4 mb-4 text-center"
      style={{
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
      }}
    >
      <p className="text-sm font-semibold mb-1" style={{ color: '#EF4444' }}>
        Insufficient balance
      </p>
      <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
        Top up your balance to purchase this plan
      </p>
      <button
        onClick={() => navigate('/')}
        className="text-xs font-semibold px-4 py-2 rounded-xl"
        style={{ backgroundColor: '#10B981', color: '#ffffff' }}
      >
        Top up balance
      </button>
    </div>
  );
}

function VpnPlans() {
  const { data, isLoading } = usePlans();
  const { data: me } = useMe();
  const buyPlan = useBuyPlan();
  const trialVpn = useTrialVpn();
  const [selectedDevices, setSelectedDevices] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showInsufficientBalance, setShowInsufficientBalance] = useState(false);

  if (isLoading || !data) {
    return <LoadingSkeleton />;
  }

  const plans = data.plans;
  const trialAvailable = me?.subscriptions.vpn.trial_available || false;

  const handleBuy = async () => {
    if (!selectedDevices || !selectedDuration) return;
    setShowInsufficientBalance(false);

    try {
      await buyPlan.mutateAsync({
        product: 'vpn',
        devices: selectedDevices,
        duration: selectedDuration,
      });
      setShowSuccess(true);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const body = err.body as { error?: string } | undefined;
        if (body?.error === 'Insufficient balance') {
          setShowInsufficientBalance(true);
        }
      }
    }
  };

  const handleTrial = async () => {
    await trialVpn.mutateAsync();
  };

  // Get price for selected plan in RUB
  const getSelectedPrice = () => {
    if (!selectedDevices || !selectedDuration) return null;
    const plan = plans.find((p) => p.devices === selectedDevices);
    if (!plan) return null;
    const rubPrices = plan.prices['RUB'] || {};
    return rubPrices[selectedDuration] || null;
  };

  const selectedPrice = getSelectedPrice();

  return (
    <div>
      {showSuccess && <PurchaseSuccessBanner onDismiss={() => setShowSuccess(false)} />}
      {showInsufficientBalance && <InsufficientBalanceBanner />}

      {trialAvailable && (
        <button
          onClick={handleTrial}
          disabled={trialVpn.isPending}
          className="w-full rounded-2xl p-4 mb-4 text-center text-sm font-semibold transition-all duration-200"
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            color: '#10B981',
            border: '1px dashed rgba(16, 185, 129, 0.4)',
          }}
        >
          {trialVpn.isPending ? 'Activating...' : '🎉 Try for Free (7 days)'}
        </button>
      )}

      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
        Select devices
      </p>
      {plans.map((plan, idx) => {
        const rubPrices = plan.prices['RUB'] || {};
        const firstDuration = plan.durations[0];
        const displayPrice = rubPrices[firstDuration] || 0;

        return (
          <PlanCard
            key={plan.devices}
            title={`${plan.devices} device${plan.devices > 1 ? 's' : ''}`}
            description={`from ${displayPrice} ₽`}
            price={displayPrice}
            currency="₽"
            popular={idx === 1}
            selected={selectedDevices === plan.devices}
            onSelect={() => {
              setSelectedDevices(plan.devices);
              if (!selectedDuration && plan.durations.length > 0) {
                setSelectedDuration(plan.durations[0]);
              }
            }}
          />
        );
      })}

      {selectedDevices && (
        <>
          <p className="text-xs font-semibold mt-4 mb-2" style={{ color: 'var(--text-muted)' }}>
            Select duration
          </p>
          {(() => {
            const plan = plans.find((p) => p.devices === selectedDevices);
            if (!plan) return null;
            const rubPrices = plan.prices['RUB'] || {};
            return plan.durations.map((d) => {
              const displayPrice = rubPrices[d] || 0;
              return (
                <PlanCard
                  key={d}
                  title={`${d} days`}
                  description=""
                  price={displayPrice}
                  currency="₽"
                  selected={selectedDuration === d}
                  onSelect={() => setSelectedDuration(d)}
                />
              );
            });
          })()}
        </>
      )}

      {selectedDevices && selectedDuration && selectedPrice !== null && (
        <button
          onClick={handleBuy}
          disabled={buyPlan.isPending}
          className="w-full rounded-2xl p-4 mt-4 text-center text-sm font-bold transition-all duration-200"
          style={{
            backgroundColor: buyPlan.isPending ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
            color: '#ffffff',
            boxShadow: buyPlan.isPending ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
          }}
        >
          {buyPlan.isPending ? 'Processing...' : `Buy for ${selectedPrice} ₽`}
        </button>
      )}

      <PromoCodeSection />
    </div>
  );
}

function PromoCodeSection() {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState('');
  const activate = useActivatePromocode();

  const handleActivate = async () => {
    if (!code.trim()) return;
    activate.mutate(
      { code: code.trim() },
      { onSuccess: () => setCode('') },
    );
  };

  if (activate.isSuccess) {
    return (
      <div
        className="rounded-2xl p-3 mt-4 text-center"
        style={{
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
        }}
      >
        <p className="text-sm font-semibold" style={{ color: '#10B981' }}>
          Promo activated! +{activate.data.duration} days
        </p>
      </div>
    );
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full mt-3 text-xs text-center transition-colors"
        style={{ color: 'var(--text-dim)' }}
      >
        Have a promo code?
      </button>
    );
  }

  const errorMessage =
    activate.error instanceof ApiRequestError
      ? ((activate.error.body as { error?: string })?.error || 'Invalid or used promo code')
      : activate.error
        ? 'Invalid or used promo code'
        : null;

  return (
    <div className="mt-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleActivate()}
          placeholder="Enter promo code"
          className="flex-1 rounded-xl px-3 py-2 text-sm outline-none transition-colors"
          style={{
            backgroundColor: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: `1px solid ${activate.isError ? 'var(--danger, #EF4444)' : 'var(--border)'}`,
          }}
          disabled={activate.isPending}
          autoFocus
        />
        <button
          onClick={handleActivate}
          disabled={activate.isPending || !code.trim()}
          className="rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-200"
          style={{
            backgroundColor: activate.isPending || !code.trim() ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
            color: '#ffffff',
          }}
        >
          {activate.isPending ? '...' : 'Apply'}
        </button>
      </div>
      {activate.isError && (
        <p className="text-xs mt-1.5 ml-1" style={{ color: 'var(--danger, #EF4444)' }}>
          {errorMessage}
        </p>
      )}
    </div>
  );
}

function ServicePlans({ product }: { product: 'mtproto' | 'whatsapp' }) {
  const mtproto = useMtprotoPlans();
  const whatsapp = useWhatsappPlans();
  const { data: me } = useMe();
  const buyPlan = useBuyPlan();
  const trialMtproto = useTrialMtproto();
  const trialWhatsapp = useTrialWhatsapp();
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showInsufficientBalance, setShowInsufficientBalance] = useState(false);

  const query = product === 'mtproto' ? mtproto : whatsapp;
  const trialMutation = product === 'mtproto' ? trialMtproto : trialWhatsapp;

  if (query.isLoading || !query.data) {
    return <LoadingSkeleton />;
  }

  const plans = query.data.plans;
  const trialAvailable =
    product === 'mtproto'
      ? me?.subscriptions.mtproto.trial_available
      : me?.subscriptions.whatsapp.trial_available;

  const handleBuy = async () => {
    if (!selectedDuration) return;
    setShowInsufficientBalance(false);

    try {
      await buyPlan.mutateAsync({
        product,
        duration: selectedDuration,
      });
      setShowSuccess(true);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const body = err.body as { error?: string } | undefined;
        if (body?.error === 'Insufficient balance') {
          setShowInsufficientBalance(true);
        }
      }
    }
  };

  const handleTrial = async () => {
    await trialMutation.mutateAsync();
  };

  return (
    <div>
      {showSuccess && <PurchaseSuccessBanner onDismiss={() => setShowSuccess(false)} />}
      {showInsufficientBalance && <InsufficientBalanceBanner />}

      {trialAvailable && (
        <button
          onClick={handleTrial}
          disabled={trialMutation.isPending}
          className="w-full rounded-2xl p-4 mb-4 text-center text-sm font-semibold transition-all duration-200"
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            color: '#10B981',
            border: '1px dashed rgba(16, 185, 129, 0.4)',
          }}
        >
          {trialMutation.isPending ? 'Activating...' : '🎉 Try for Free (3 days)'}
        </button>
      )}

      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
        Select duration
      </p>
      {plans.map((plan) => (
        <PlanCard
          key={plan.duration}
          title={`${plan.duration} days`}
          description=""
          price={plan.price_rub}
          currency="₽"
          selected={selectedDuration === plan.duration}
          onSelect={() => setSelectedDuration(plan.duration)}
        />
      ))}

      {selectedDuration && (() => {
        const selectedPlan = plans.find((p) => p.duration === selectedDuration);
        if (!selectedPlan) return null;
        return (
          <button
            onClick={handleBuy}
            disabled={buyPlan.isPending}
            className="w-full rounded-2xl p-4 mt-4 text-center text-sm font-bold transition-all duration-200"
            style={{
              backgroundColor: buyPlan.isPending ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
              color: '#ffffff',
              boxShadow: buyPlan.isPending ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
            }}
          >
            {buyPlan.isPending ? 'Processing...' : `Buy for ${selectedPlan.price_rub} ₽`}
          </button>
        );
      })()}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="animate-shimmer rounded-2xl h-16" />
      ))}
    </div>
  );
}
