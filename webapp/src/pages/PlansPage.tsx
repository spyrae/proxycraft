import { useState, useMemo } from 'react';
import {
  useMe,
  usePlans,
  useMtprotoPlans,
  useWhatsappPlans,
  useTrialVpn,
  useTrialMtproto,
  useTrialWhatsapp,
  useActivatePromocode,
} from '../api/hooks';
import { ApiRequestError } from '../api/client';
import { usePayment } from '../hooks/usePayment';
import { PlanCard } from '../components/PlanCard';

type Tab = 'vpn' | 'mtproto' | 'whatsapp';
type Currency = 'stars' | 'rub';

function useSavedCurrency(): [Currency, (c: Currency) => void] {
  const [currency, setCurrency] = useState<Currency>(() => {
    try {
      return (localStorage.getItem('vpncraft_currency') as Currency) || 'stars';
    } catch {
      return 'stars';
    }
  });

  const save = (c: Currency) => {
    setCurrency(c);
    try {
      localStorage.setItem('vpncraft_currency', c);
    } catch {}
  };

  return [currency, save];
}

export function PlansPage() {
  const { data: me } = useMe();
  const [tab, setTab] = useState<Tab>('vpn');
  const [currency, setCurrency] = useSavedCurrency();

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

      {/* Currency toggle */}
      <div
        className="flex rounded-xl p-1 mb-4"
        style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <CurrencyButton
          active={currency === 'stars'}
          onClick={() => setCurrency('stars')}
          label="★ Stars"
        />
        <CurrencyButton
          active={currency === 'rub'}
          onClick={() => setCurrency('rub')}
          label="₽ Рубли"
        />
      </div>

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

      {tab === 'vpn' && <VpnPlans currency={currency} />}
      {tab === 'mtproto' && <ServicePlans product="mtproto" currency={currency} />}
      {tab === 'whatsapp' && <ServicePlans product="whatsapp" currency={currency} />}

      {currency === 'rub' && (
        <p className="text-[10px] text-center mt-3" style={{ color: 'var(--text-dim)' }}>
          Оплата через Т-Банк
        </p>
      )}
    </div>
  );
}

function CurrencyButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className="flex-1 text-sm font-semibold py-2 rounded-lg transition-all duration-200"
      style={{
        backgroundColor: active ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
        color: active ? '#10B981' : 'var(--text-dim)',
      }}
    >
      {label}
    </button>
  );
}

function PaymentPendingBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div
      className="rounded-2xl p-4 mb-4 text-center"
      style={{
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        border: '1px solid rgba(16, 185, 129, 0.3)',
      }}
    >
      <p className="text-sm font-semibold mb-1" style={{ color: '#10B981' }}>
        Оплата обрабатывается
      </p>
      <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
        После подтверждения платежа подписка активируется автоматически
      </p>
      <button
        onClick={onDismiss}
        className="text-xs font-medium px-3 py-1 rounded-lg"
        style={{ color: 'var(--text-dim)' }}
      >
        Скрыть
      </button>
    </div>
  );
}

function VpnPlans({ currency }: { currency: Currency }) {
  const { data, isLoading } = usePlans();
  const { data: me } = useMe();
  const { pay, status: paymentStatus, isLoading: paying } = usePayment();
  const trialVpn = useTrialVpn();
  const [selectedDevices, setSelectedDevices] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);

  if (isLoading || !data) {
    return <LoadingSkeleton />;
  }

  const plans = data.plans;
  const isExtend = me?.subscriptions.vpn.active || false;
  const trialAvailable = me?.subscriptions.vpn.trial_available || false;

  const [showPending, setShowPending] = useState(false);

  const handleBuy = async () => {
    if (!selectedDevices || !selectedDuration) return;
    const result = await pay({
      product: 'vpn',
      devices: selectedDevices,
      duration: selectedDuration,
      is_extend: isExtend,
      currency,
    });
    if (result === 'pending') {
      setShowPending(true);
    }
  };

  const handleTrial = async () => {
    await trialVpn.mutateAsync();
  };

  return (
    <div>
      {(showPending || paymentStatus === 'pending_external') && (
        <PaymentPendingBanner onDismiss={() => setShowPending(false)} />
      )}

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
        const durations = plan.durations;
        const firstDuration = durations[0];
        const starsPrice = (plan.prices['XTR'] || {})[firstDuration] || 0;
        const rubPrice = (plan.prices['RUB'] || {})[firstDuration] || 0;
        const displayPrice = currency === 'rub' ? rubPrice : starsPrice;
        const displayCurrency = currency === 'rub' ? '₽' : '★';

        return (
          <PlanCard
            key={plan.devices}
            title={`${plan.devices} device${plan.devices > 1 ? 's' : ''}`}
            description={`from ${displayPrice} ${displayCurrency}`}
            price={displayPrice}
            currency={displayCurrency}
            popular={idx === 1}
            selected={selectedDevices === plan.devices}
            onSelect={() => {
              setSelectedDevices(plan.devices);
              if (!selectedDuration && durations.length > 0) {
                setSelectedDuration(durations[0]);
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
            const starsPrices = plan.prices['XTR'] || {};
            const rubPrices = plan.prices['RUB'] || {};
            return plan.durations.map((d) => {
              const displayPrice = currency === 'rub' ? (rubPrices[d] || 0) : (starsPrices[d] || 0);
              const displayCurrency = currency === 'rub' ? '₽' : '★';
              return (
                <PlanCard
                  key={d}
                  title={`${d} days`}
                  description=""
                  price={displayPrice}
                  currency={displayCurrency}
                  selected={selectedDuration === d}
                  onSelect={() => setSelectedDuration(d)}
                />
              );
            });
          })()}
        </>
      )}

      {selectedDevices && selectedDuration && (
        <button
          onClick={handleBuy}
          disabled={paying}
          className="w-full rounded-2xl p-4 mt-4 text-center text-sm font-bold transition-all duration-200"
          style={{
            backgroundColor: paying ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
            color: '#ffffff',
            boxShadow: paying ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
          }}
        >
          {paying ? 'Processing...' : currency === 'rub' ? 'Pay ₽' : 'Pay with Stars ★'}
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
          Промокод активирован! +{activate.data.duration} дней
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
        Есть промокод?
      </button>
    );
  }

  const errorMessage =
    activate.error instanceof ApiRequestError
      ? ((activate.error.body as { error?: string })?.error || 'Неверный или использованный промокод')
      : activate.error
        ? 'Неверный или использованный промокод'
        : null;

  return (
    <div className="mt-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleActivate()}
          placeholder="Введите промокод"
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
          {activate.isPending ? '...' : 'Применить'}
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

function ServicePlans({ product, currency }: { product: 'mtproto' | 'whatsapp'; currency: Currency }) {
  const mtproto = useMtprotoPlans();
  const whatsapp = useWhatsappPlans();
  const { data: me } = useMe();
  const { pay, status: paymentStatus, isLoading: paying } = usePayment();
  const trialMtproto = useTrialMtproto();
  const trialWhatsapp = useTrialWhatsapp();
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);

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
  const isExtend =
    product === 'mtproto'
      ? me?.subscriptions.mtproto.active
      : me?.subscriptions.whatsapp.active;

  const [showPending, setShowPending] = useState(false);

  const handleBuy = async () => {
    if (!selectedDuration) return;
    const result = await pay({
      product,
      duration: selectedDuration,
      is_extend: isExtend || false,
      currency,
    });
    if (result === 'pending') {
      setShowPending(true);
    }
  };

  const handleTrial = async () => {
    await trialMutation.mutateAsync();
  };

  return (
    <div>
      {(showPending || paymentStatus === 'pending_external') && (
        <PaymentPendingBanner onDismiss={() => setShowPending(false)} />
      )}

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
      {plans.map((plan) => {
        const displayPrice = currency === 'rub' ? plan.price_rub : plan.price_stars;
        const displayCurrency = currency === 'rub' ? '₽' : '★';
        return (
          <PlanCard
            key={plan.duration}
            title={`${plan.duration} days`}
            description={currency === 'rub' ? `${plan.price_stars} ★` : `${plan.price_rub} ₽`}
            price={displayPrice}
            currency={displayCurrency}
            selected={selectedDuration === plan.duration}
            onSelect={() => setSelectedDuration(plan.duration)}
          />
        );
      })}

      {selectedDuration && (
        <button
          onClick={handleBuy}
          disabled={paying}
          className="w-full rounded-2xl p-4 mt-4 text-center text-sm font-bold transition-all duration-200"
          style={{
            backgroundColor: paying ? 'rgba(16, 185, 129, 0.5)' : '#10B981',
            color: '#ffffff',
            boxShadow: paying ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
          }}
        >
          {paying ? 'Processing...' : currency === 'rub' ? 'Pay ₽' : 'Pay with Stars ★'}
        </button>
      )}
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
