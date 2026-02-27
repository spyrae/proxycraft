import { useMe, useVpnSubscription, useMtprotoSubscription, useWhatsappSubscription } from '../api/hooks';
import { SubscriptionCard } from '../components/SubscriptionCard';
import { QRCode } from '../components/QRCode';
import { CopyButton } from '../components/CopyButton';

export function MyVpnPage() {
  const { data: me } = useMe();

  return (
    <div>
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        My VPN
      </h1>

      <VpnSection />

      {me?.features.mtproto_enabled && <MtprotoSection />}
      {me?.features.whatsapp_enabled && <WhatsappSection />}
    </div>
  );
}

function VpnSection() {
  const { data: sub, isLoading } = useVpnSubscription();

  if (isLoading) return <SkeletonCard />;
  if (!sub) return null;

  const status = sub.active ? 'active' : sub.expired ? 'expired' : 'none';

  return (
    <SubscriptionCard title="VPN" status={status}>
      {sub.active && (
        <div className="space-y-3">
          {/* Traffic stats */}
          <div className="grid grid-cols-2 gap-2">
            <StatItem label="Upload" value={formatBytes(sub.traffic_up || 0)} />
            <StatItem label="Download" value={formatBytes(sub.traffic_down || 0)} />
            <StatItem label="Total Used" value={formatBytes(sub.traffic_used || 0)} />
            <StatItem label="Devices" value={sub.max_devices === -1 ? 'Unlimited' : String(sub.max_devices)} />
          </div>

          {sub.expiry_time && sub.expiry_time > 0 && (
            <div className="text-xs" style={{ color: 'var(--text-hint)' }}>
              Expires: {new Date(sub.expiry_time).toLocaleDateString()}
            </div>
          )}

          {/* Subscription key + QR */}
          {sub.key && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div
                  className="flex-1 text-xs font-mono p-2 rounded-lg overflow-hidden text-ellipsis whitespace-nowrap"
                  style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                >
                  {sub.key}
                </div>
                <CopyButton text={sub.key} />
              </div>
              <QRCode value={sub.key} />
            </div>
          )}
        </div>
      )}

      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-hint)' }}>
          {sub.expired ? 'Your subscription has expired.' : 'No active VPN subscription.'}
        </p>
      )}
    </SubscriptionCard>
  );
}

function MtprotoSection() {
  const { data: sub, isLoading } = useMtprotoSubscription();

  if (isLoading) return <SkeletonCard />;
  if (!sub) return null;

  const status = sub.active ? 'active' : sub.expired ? 'expired' : 'none';

  return (
    <SubscriptionCard title="MTProto Proxy" status={status}>
      {sub.active && sub.link && (
        <div className="space-y-3">
          {sub.expires_at && (
            <div className="text-xs" style={{ color: 'var(--text-hint)' }}>
              Expires: {new Date(sub.expires_at).toLocaleDateString()}
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className="flex-1 text-xs font-mono p-2 rounded-lg overflow-hidden text-ellipsis whitespace-nowrap"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              {sub.link}
            </div>
            <CopyButton text={sub.link} />
          </div>
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-hint)' }}>
          No active MTProto subscription.
        </p>
      )}
    </SubscriptionCard>
  );
}

function WhatsappSection() {
  const { data: sub, isLoading } = useWhatsappSubscription();

  if (isLoading) return <SkeletonCard />;
  if (!sub) return null;

  const status = sub.active ? 'active' : sub.expired ? 'expired' : 'none';
  const connectionString = sub.active && sub.host && sub.port ? `${sub.host}:${sub.port}` : null;

  return (
    <SubscriptionCard title="WhatsApp Proxy" status={status}>
      {sub.active && connectionString && (
        <div className="space-y-3">
          {sub.expires_at && (
            <div className="text-xs" style={{ color: 'var(--text-hint)' }}>
              Expires: {new Date(sub.expires_at).toLocaleDateString()}
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className="flex-1 text-xs font-mono p-2 rounded-lg"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              {connectionString}
            </div>
            <CopyButton text={connectionString} />
          </div>
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-hint)' }}>
          No active WhatsApp subscription.
        </p>
      )}
    </SubscriptionCard>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-lg p-2"
      style={{ backgroundColor: 'var(--bg-secondary)' }}
    >
      <div className="text-[10px] mb-0.5" style={{ color: 'var(--text-hint)' }}>
        {label}
      </div>
      <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div
      className="rounded-xl h-32 mb-3 animate-pulse"
      style={{ backgroundColor: 'var(--section-bg)' }}
    />
  );
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(value < 10 ? 2 : 1)} ${units[i]}`;
}
