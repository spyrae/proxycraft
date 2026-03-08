import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopupModal } from '../components/TopupModal';
import { useLanguage } from '../i18n/LanguageContext';
import type { Lang } from '../i18n/translations';

function deviceLabel(n: number, lang: Lang): string {
  if (lang !== 'ru') return n === 1 ? `${n} device` : `${n} devices`;
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} устройство`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return `${n} устройства`;
  return `${n} устройств`;
}
import {
  useMe,
  usePlans,
  useMtprotoPlans,
  useWhatsappPlans,
  useLocations,
  useTrialVpn,
  useTrialMtproto,
  useTrialWhatsapp,
  useActivatePromocode,
  useBuyPlan,
} from '../api/hooks';
import { ApiRequestError } from '../api/client';
import { PlanCard } from '../components/PlanCard';
import { StatusOverlay } from '../components/StatusOverlay';
import type { OverlayMode } from '../components/StatusOverlay';

type Tab = 'vpn' | 'mtproto' | 'whatsapp';

const LOCATION_FLAGS: Record<string, string> = {
  'Amsterdam': '🇳🇱',
  'Saint Petersburg': '🇷🇺',
};

const LOCATION_KEYS: Record<string, string> = {
  'Amsterdam': 'loc_amsterdam',
  'Saint Petersburg': 'loc_saint_petersburg',
};

// Locations incompatible with Telegram/WhatsApp proxy
const PROXY_INCOMPATIBLE_LOCATIONS = new Set(['Saint Petersburg']);
// Products incompatible with Saint Petersburg
const SPB_INCOMPATIBLE_PRODUCTS = new Set<Tab>(['mtproto', 'whatsapp']);

export function PlansPage() {
  const { data: me } = useMe();
  const { data: locData } = useLocations();
  const [tab, setTab] = useState<Tab>('vpn');
  const [location, setLocation] = useState<string | null>(null);
  const { t } = useLanguage();

  const locations = locData?.locations || [];

  useEffect(() => {
    if (locations.length > 0 && location === null) {
      setLocation(locations[0].name);
    }
  }, [locations, location]);

  const tabs: { key: Tab; label: string }[] = useMemo(() => {
    const tabList: { key: Tab; label: string }[] = [{ key: 'vpn', label: 'VPN' }];
    if (me?.features.mtproto_enabled) tabList.push({ key: 'mtproto', label: 'Telegram' });
    if (me?.features.whatsapp_enabled) tabList.push({ key: 'whatsapp', label: 'WhatsApp' });
    return tabList;
  }, [me]);

  // When selecting a proxy-incompatible location, force tab to VPN
  const handleLocationChange = (locName: string) => {
    setLocation(locName);
    if (PROXY_INCOMPATIBLE_LOCATIONS.has(locName) && SPB_INCOMPATIBLE_PRODUCTS.has(tab)) {
      setTab('vpn');
    }
  };

  // When selecting Telegram/WhatsApp, force location away from SPb
  const handleTabChange = (newTab: Tab) => {
    setTab(newTab);
    if (SPB_INCOMPATIBLE_PRODUCTS.has(newTab) && location && PROXY_INCOMPATIBLE_LOCATIONS.has(location)) {
      const firstCompatible = locations.find((l) => !PROXY_INCOMPATIBLE_LOCATIONS.has(l.name));
      if (firstCompatible) setLocation(firstCompatible.name);
    }
  };

  const isProxyIncompatibleLocation = location ? PROXY_INCOMPATIBLE_LOCATIONS.has(location) : false;

  return (
    <div className="animate-fade-in">
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        {t('plans_title')}
      </h1>

      {/* Balance info */}
      {me && (
        <BalanceBanner balance={me.balance} />
      )}

      {/* Location selector */}
      {locations.length > 1 && (
        <div className="mb-4">
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
            {t('location')}
          </p>
          <div
            className="flex rounded-xl p-1"
            style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            {locations.map((loc) => {
              const active = location === loc.name;
              const flag = LOCATION_FLAGS[loc.name] || '🌐';
              const disabledByProduct = SPB_INCOMPATIBLE_PRODUCTS.has(tab) && PROXY_INCOMPATIBLE_LOCATIONS.has(loc.name);
              return (
                <button
                  key={loc.name}
                  onClick={() => handleLocationChange(loc.name)}
                  disabled={disabledByProduct}
                  className="flex-1 flex items-center justify-center gap-1.5 text-sm font-semibold py-2 rounded-lg transition-all duration-200"
                  style={{
                    backgroundColor: active ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                    color: active ? '#10B981' : 'var(--text-dim)',
                    opacity: (loc.available && !disabledByProduct) ? 1 : 0.4,
                  }}
                >
                  <span>{flag}</span>
                  {LOCATION_KEYS[loc.name] ? t(LOCATION_KEYS[loc.name] as Parameters<typeof t>[0]) : loc.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Segment control */}
      {tabs.length > 1 && (
        <div
          className="flex rounded-xl p-1 mb-4"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          {tabs.map((tabItem) => {
            const disabledByLocation = isProxyIncompatibleLocation && SPB_INCOMPATIBLE_PRODUCTS.has(tabItem.key);
            return (
              <button
                key={tabItem.key}
                onClick={() => handleTabChange(tabItem.key)}
                disabled={disabledByLocation}
                className="flex-1 text-sm font-semibold py-2 rounded-lg transition-all duration-200"
                style={{
                  backgroundColor: tab === tabItem.key ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                  color: tab === tabItem.key ? '#10B981' : 'var(--text-dim)',
                  opacity: disabledByLocation ? 0.4 : 1,
                }}
              >
                {tabItem.label}
              </button>
            );
          })}
        </div>
      )}

      {tab === 'vpn' && <VpnPlans location={location} />}
      {tab === 'mtproto' && <ServicePlans product="mtproto" />}
      {tab === 'whatsapp' && <ServicePlans product="whatsapp" />}
    </div>
  );
}

const STARS_RATE = 1.8;

function BalanceBanner({ balance }: { balance: number }) {
  const [showTopup, setShowTopup] = useState(false);
  const { t, lang } = useLanguage();
  const displayBalance = lang === 'en'
    ? `⭐ ${Math.round(balance / STARS_RATE)}`
    : `${balance.toFixed(0)} ₽`;

  return (
    <>
      <div
        className="flex items-center justify-between rounded-2xl p-3 mb-4"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
            {t('balance_plans')}
          </span>
          <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            {displayBalance}
          </span>
        </div>
        <button
          onClick={() => setShowTopup(true)}
          className="text-xs font-semibold px-3 py-1 rounded-lg"
          style={{ color: '#10B981' }}
        >
          {t('top_up')}
        </button>
      </div>

      {showTopup && <TopupModal onClose={() => setShowTopup(false)} />}
    </>
  );
}


function InsufficientBalanceBanner({ onTopup }: { onTopup: () => void }) {
  const { t } = useLanguage();
  return (
    <div
      className="rounded-2xl p-4 mb-4 text-center"
      style={{
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
      }}
    >
      <p className="text-sm font-semibold mb-1" style={{ color: '#EF4444' }}>
        {t('insufficient_bal')}
      </p>
      <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
        {t('topup_to_purchase')}
      </p>
      <button
        onClick={onTopup}
        className="text-xs font-semibold px-4 py-2 rounded-xl"
        style={{ backgroundColor: '#10B981', color: '#ffffff' }}
      >
        {t('top_up_balance')}
      </button>
    </div>
  );
}

function VpnPlans({ location }: { location: string | null }) {
  const { data, isLoading } = usePlans();
  const { data: me } = useMe();
  const buyPlan = useBuyPlan();
  const trialVpn = useTrialVpn();
  const navigate = useNavigate();
  const { t, lang } = useLanguage();
  const [selectedDevices, setSelectedDevices] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('hidden');
  const [showInsufficientBalance, setShowInsufficientBalance] = useState(false);
  const [showTopup, setShowTopup] = useState(false);

  if (isLoading || !data) {
    return <LoadingSkeleton />;
  }

  const plans = data.plans;
  const trialAvailable = me?.subscriptions.vpn.trial_available || false;

  const handleBuy = async () => {
    if (!selectedDevices || !selectedDuration) return;
    setShowInsufficientBalance(false);
    setOverlayMode('loading');

    try {
      await buyPlan.mutateAsync({
        product: 'vpn',
        devices: selectedDevices,
        duration: selectedDuration,
        ...(location && { location }),
      });
      setOverlayMode('success');
    } catch (err) {
      setOverlayMode('hidden');
      if (err instanceof ApiRequestError) {
        const body = err.body as { error?: string } | undefined;
        if (body?.error === 'Insufficient balance') {
          setShowInsufficientBalance(true);
        }
      }
    }
  };

  const handleTrial = async () => {
    setOverlayMode('loading');
    try {
      await trialVpn.mutateAsync();
      setOverlayMode('success');
    } catch {
      setOverlayMode('hidden');
    }
  };

  const priceKey = lang === 'en' ? 'XTR' : 'RUB';
  const currencySymbol = lang === 'en' ? '⭐' : '₽';

  // Get price for selected plan
  const getSelectedPrice = () => {
    if (!selectedDevices || !selectedDuration) return null;
    const plan = plans.find((p) => p.devices === selectedDevices);
    if (!plan) return null;
    const prices = plan.prices[priceKey] || {};
    return prices[selectedDuration] || null;
  };

  const selectedPrice = getSelectedPrice();

  return (
    <div>
      {showTopup && <TopupModal onClose={() => setShowTopup(false)} />}
      <StatusOverlay mode={overlayMode} loadingKey="activating" onDismiss={() => { setOverlayMode('hidden'); navigate('/my-vpn'); }} />
      {showInsufficientBalance && <InsufficientBalanceBanner onTopup={() => { setShowInsufficientBalance(false); setShowTopup(true); }} />}

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
          {trialVpn.isPending ? t('activating') : t('try_free_7')}
        </button>
      )}

      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
        {t('select_devices')}
      </p>
      {plans.map((plan, idx) => {
        const prices = plan.prices[priceKey] || {};
        const firstDuration = plan.durations[0];
        const displayPrice = prices[firstDuration] || 0;

        return (
          <PlanCard
            key={plan.devices}
            title={deviceLabel(plan.devices, lang)}
            description={t('from_price', { price: displayPrice })}
            price={displayPrice}
            currency={currencySymbol}
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
            {t('select_duration')}
          </p>
          {(() => {
            const plan = plans.find((p) => p.devices === selectedDevices);
            if (!plan) return null;
            const prices = plan.prices[priceKey] || {};
            return plan.durations.map((d) => {
              const displayPrice = prices[d] || 0;
              return (
                <PlanCard
                  key={d}
                  title={t('n_days', { d })}
                  description=""
                  price={displayPrice}
                  currency={currencySymbol}
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
          {buyPlan.isPending ? t('processing') : t('buy_for', { price: selectedPrice })}
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
  const { t } = useLanguage();

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
          {t('promo_activated', { days: activate.data.duration })}
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
        {t('have_promo')}
      </button>
    );
  }

  const errorMessage =
    activate.error instanceof ApiRequestError
      ? ((activate.error.body as { error?: string })?.error || t('invalid_promo'))
      : activate.error
        ? t('invalid_promo')
        : null;

  return (
    <div className="mt-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleActivate()}
          placeholder={t('promo_placeholder')}
          className="flex-1 min-w-0 rounded-xl px-3 py-2 text-sm outline-none transition-colors"
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
          {activate.isPending ? '...' : t('apply')}
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
  const navigate = useNavigate();
  const { t, lang } = useLanguage();
  const currencySymbol = lang === 'en' ? '⭐' : '₽';
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('hidden');
  const [showInsufficientBalance, setShowInsufficientBalance] = useState(false);
  const [showTopup, setShowTopup] = useState(false);

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
    setOverlayMode('loading');

    try {
      await buyPlan.mutateAsync({
        product,
        duration: selectedDuration,
      });
      setOverlayMode('success');
    } catch (err) {
      setOverlayMode('hidden');
      if (err instanceof ApiRequestError) {
        const body = err.body as { error?: string } | undefined;
        if (body?.error === 'Insufficient balance') {
          setShowInsufficientBalance(true);
        }
      }
    }
  };

  const handleTrial = async () => {
    setOverlayMode('loading');
    try {
      await trialMutation.mutateAsync();
      setOverlayMode('success');
    } catch {
      setOverlayMode('hidden');
    }
  };

  return (
    <div>
      {showTopup && <TopupModal onClose={() => setShowTopup(false)} />}
      <StatusOverlay mode={overlayMode} loadingKey="activating" onDismiss={() => { setOverlayMode('hidden'); navigate('/my-vpn'); }} />
      {showInsufficientBalance && <InsufficientBalanceBanner onTopup={() => { setShowInsufficientBalance(false); setShowTopup(true); }} />}

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
          {trialMutation.isPending ? t('activating') : t('try_free_3')}
        </button>
      )}

      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
        {t('select_duration')}
      </p>
      {plans.map((plan) => {
        const displayPrice = lang === 'en' ? plan.price_stars : plan.price_rub;
        return (
          <PlanCard
            key={plan.duration}
            title={t('n_days', { d: plan.duration })}
            description=""
            price={displayPrice}
            currency={currencySymbol}
            selected={selectedDuration === plan.duration}
            onSelect={() => setSelectedDuration(plan.duration)}
          />
        );
      })}

      {selectedDuration && (() => {
        const selectedPlan = plans.find((p) => p.duration === selectedDuration);
        if (!selectedPlan) return null;
        const displayPrice = lang === 'en' ? selectedPlan.price_stars : selectedPlan.price_rub;
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
            {buyPlan.isPending ? t('processing') : t('buy_for', { price: displayPrice })}
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
