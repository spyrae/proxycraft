import { useState, useMemo } from 'react';
import {
  useMe,
  usePlans,
  useMtprotoPlans,
  useWhatsappPlans,
  useTrialVpn,
  useTrialMtproto,
  useTrialWhatsapp,
} from '../api/hooks';
import { usePayment } from '../hooks/usePayment';
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
    <div>
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        Plans
      </h1>

      {/* Segment control */}
      {tabs.length > 1 && (
        <div
          className="flex rounded-lg p-0.5 mb-4"
          style={{ backgroundColor: 'var(--bg-secondary)' }}
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex-1 text-sm font-medium py-2 rounded-md transition-all"
              style={{
                backgroundColor: tab === t.key ? 'var(--section-bg)' : 'transparent',
                color: tab === t.key ? 'var(--text-primary)' : 'var(--text-hint)',
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

function VpnPlans() {
  const { data, isLoading } = usePlans();
  const { data: me } = useMe();
  const { pay, isLoading: paying } = usePayment();
  const trialVpn = useTrialVpn();
  const [selectedDevices, setSelectedDevices] = useState<number | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);

  if (isLoading || !data) {
    return <LoadingSkeleton />;
  }

  const plans = data.plans;
  const isExtend = me?.subscriptions.vpn.active || false;
  const trialAvailable = me?.subscriptions.vpn.trial_available || false;

  const handleBuy = async () => {
    if (!selectedDevices || !selectedDuration) return;
    await pay({
      product: 'vpn',
      devices: selectedDevices,
      duration: selectedDuration,
      is_extend: isExtend,
    });
  };

  const handleTrial = async () => {
    await trialVpn.mutateAsync();
  };

  return (
    <div>
      {trialAvailable && (
        <button
          onClick={handleTrial}
          disabled={trialVpn.isPending}
          className="w-full rounded-xl p-4 mb-4 text-center text-sm font-semibold transition-all"
          style={{
            backgroundColor: '#34c75920',
            color: '#34c759',
            border: '1px dashed #34c759',
          }}
        >
          {trialVpn.isPending ? 'Activating...' : 'Try for Free (7 days)'}
        </button>
      )}

      <p className="text-xs font-medium mb-2" style={{ color: 'var(--text-hint)' }}>
        Select number of devices
      </p>
      {plans.map((plan) => {
        const durations = plan.durations;
        const firstDuration = durations[0];
        const prices = plan.prices['XTR'] || {};
        const firstPrice = prices[firstDuration] || 0;

        return (
          <PlanCard
            key={plan.devices}
            title={`${plan.devices} device${plan.devices > 1 ? 's' : ''}`}
            description={`from ${firstPrice} Stars`}
            price={firstPrice}
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
          <p className="text-xs font-medium mt-4 mb-2" style={{ color: 'var(--text-hint)' }}>
            Select duration
          </p>
          {(() => {
            const plan = plans.find((p) => p.devices === selectedDevices);
            if (!plan) return null;
            const prices = plan.prices['XTR'] || {};
            return plan.durations.map((d) => (
              <PlanCard
                key={d}
                title={`${d} days`}
                description=""
                price={prices[d] || 0}
                selected={selectedDuration === d}
                onSelect={() => setSelectedDuration(d)}
              />
            ));
          })()}
        </>
      )}

      {selectedDevices && selectedDuration && (
        <button
          onClick={handleBuy}
          disabled={paying}
          className="w-full rounded-xl p-4 mt-4 text-center text-sm font-bold transition-all"
          style={{ backgroundColor: 'var(--accent)', color: 'var(--accent-text)', opacity: paying ? 0.6 : 1 }}
        >
          {paying ? 'Processing...' : `Pay with Stars`}
        </button>
      )}
    </div>
  );
}

function ServicePlans({ product }: { product: 'mtproto' | 'whatsapp' }) {
  const mtproto = useMtprotoPlans();
  const whatsapp = useWhatsappPlans();
  const { data: me } = useMe();
  const { pay, isLoading: paying } = usePayment();
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

  const handleBuy = async () => {
    if (!selectedDuration) return;
    await pay({
      product,
      duration: selectedDuration,
      is_extend: isExtend || false,
    });
  };

  const handleTrial = async () => {
    await trialMutation.mutateAsync();
  };

  return (
    <div>
      {trialAvailable && (
        <button
          onClick={handleTrial}
          disabled={trialMutation.isPending}
          className="w-full rounded-xl p-4 mb-4 text-center text-sm font-semibold transition-all"
          style={{
            backgroundColor: '#34c75920',
            color: '#34c759',
            border: '1px dashed #34c759',
          }}
        >
          {trialMutation.isPending ? 'Activating...' : 'Try for Free (3 days)'}
        </button>
      )}

      <p className="text-xs font-medium mb-2" style={{ color: 'var(--text-hint)' }}>
        Select duration
      </p>
      {plans.map((plan) => (
        <PlanCard
          key={plan.duration}
          title={`${plan.duration} days`}
          description={`${plan.price_rub} RUB`}
          price={plan.price_stars}
          selected={selectedDuration === plan.duration}
          onSelect={() => setSelectedDuration(plan.duration)}
        />
      ))}

      {selectedDuration && (
        <button
          onClick={handleBuy}
          disabled={paying}
          className="w-full rounded-xl p-4 mt-4 text-center text-sm font-bold transition-all"
          style={{ backgroundColor: 'var(--accent)', color: 'var(--accent-text)', opacity: paying ? 0.6 : 1 }}
        >
          {paying ? 'Processing...' : 'Pay with Stars'}
        </button>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-xl h-16 animate-pulse"
          style={{ backgroundColor: 'var(--section-bg)' }}
        />
      ))}
    </div>
  );
}
