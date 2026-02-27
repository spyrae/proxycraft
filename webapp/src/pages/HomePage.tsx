import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { useMe } from '../api/hooks';
import { SubscriptionCard } from '../components/SubscriptionCard';

export function HomePage() {
  const navigate = useNavigate();
  const { user } = useTelegram();
  const { data: me, isLoading, error } = useMe();

  if (isLoading) {
    return <LoadingState />;
  }

  if (error || !me) {
    return <ErrorState />;
  }

  const vpnStatus = me.subscriptions.vpn.active ? 'active' : 'none';
  const mtprotoStatus = me.subscriptions.mtproto.active ? 'active' : 'none';
  const whatsappStatus = me.subscriptions.whatsapp.active ? 'active' : 'none';

  return (
    <div>
      {/* Greeting */}
      <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
        Hi, {user?.first_name || me.first_name}!
      </h1>
      <p className="text-sm mb-5" style={{ color: 'var(--text-hint)' }}>
        Manage your VPN subscriptions
      </p>

      {/* VPN Status */}
      <SubscriptionCard title="VPN" status={vpnStatus}>
        {vpnStatus === 'none' && me.subscriptions.vpn.trial_available && (
          <p className="text-xs" style={{ color: 'var(--text-link)' }}>
            Free trial available!
          </p>
        )}
      </SubscriptionCard>

      {/* MTProto */}
      {me.features.mtproto_enabled && (
        <SubscriptionCard title="MTProto Proxy" status={mtprotoStatus}>
          {mtprotoStatus === 'none' && me.subscriptions.mtproto.trial_available && (
            <p className="text-xs" style={{ color: 'var(--text-link)' }}>
              Free trial available!
            </p>
          )}
        </SubscriptionCard>
      )}

      {/* WhatsApp */}
      {me.features.whatsapp_enabled && (
        <SubscriptionCard title="WhatsApp Proxy" status={whatsappStatus}>
          {whatsappStatus === 'none' && me.subscriptions.whatsapp.trial_available && (
            <p className="text-xs" style={{ color: 'var(--text-link)' }}>
              Free trial available!
            </p>
          )}
        </SubscriptionCard>
      )}

      {/* Quick Links */}
      <div className="grid grid-cols-2 gap-3 mt-4">
        <QuickLink label="View Plans" onClick={() => navigate('/plans')} />
        <QuickLink label="My VPN" onClick={() => navigate('/my-vpn')} />
      </div>
    </div>
  );
}

function QuickLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-xl p-3 text-sm font-medium text-center"
      style={{ backgroundColor: 'var(--accent)', color: 'var(--accent-text)' }}
    >
      {label}
    </button>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-60">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-t-transparent" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
    </div>
  );
}

function ErrorState() {
  return (
    <div className="flex flex-col items-center justify-center h-60 gap-2">
      <p className="text-sm" style={{ color: 'var(--text-hint)' }}>Failed to load profile</p>
      <button
        onClick={() => window.location.reload()}
        className="text-sm font-medium px-4 py-2 rounded-lg"
        style={{ backgroundColor: 'var(--accent)', color: 'var(--accent-text)' }}
      >
        Retry
      </button>
    </div>
  );
}
