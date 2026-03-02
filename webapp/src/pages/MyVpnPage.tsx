import { useMe, useVpnSubscription, useMtprotoSubscription, useWhatsappSubscription } from '../api/hooks';
import { SubscriptionCard } from '../components/SubscriptionCard';
import { QRCode } from '../components/QRCode';
import { CopyButton } from '../components/CopyButton';

export function MyVpnPage() {
  const { data: me } = useMe();

  return (
    <div className="animate-fade-in">
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
            <StatItem label="Upload" value={formatBytes(sub.traffic_up || 0)} icon="↑" color="#06B6D4" />
            <StatItem label="Download" value={formatBytes(sub.traffic_down || 0)} icon="↓" color="#10B981" />
            <StatItem label="Total Used" value={formatBytes(sub.traffic_used || 0)} icon="◎" color="#8B5CF6" />
            <StatItem label="Devices" value={sub.max_devices === -1 ? '∞' : String(sub.max_devices)} icon="⊞" color="#F59E0B" />
          </div>

          {sub.expiry_time && sub.expiry_time > 0 && (
            <div
              className="flex items-center gap-2 text-xs px-3 py-2 rounded-xl"
              style={{
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                color: 'var(--text-muted)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              Expires {new Date(sub.expiry_time).toLocaleDateString()}
            </div>
          )}

          {/* Subscription key + QR */}
          {sub.key && (
            <div className="space-y-3">
              <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                Connection Key
              </p>
              <div className="flex items-center gap-2">
                <div
                  className="flex-1 text-[11px] font-mono p-2.5 rounded-xl overflow-hidden text-ellipsis whitespace-nowrap"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border)',
                  }}
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
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
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
            <div
              className="flex items-center gap-2 text-xs px-3 py-2 rounded-xl"
              style={{
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                color: 'var(--text-muted)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              Expires {new Date(sub.expires_at).toLocaleDateString()}
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className="flex-1 text-[11px] font-mono p-2.5 rounded-xl overflow-hidden text-ellipsis whitespace-nowrap"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border)',
              }}
            >
              {sub.link}
            </div>
            <CopyButton text={sub.link} />
          </div>
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
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
            <div
              className="flex items-center gap-2 text-xs px-3 py-2 rounded-xl"
              style={{
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                color: 'var(--text-muted)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              Expires {new Date(sub.expires_at).toLocaleDateString()}
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className="flex-1 text-[11px] font-mono p-2.5 rounded-xl"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border)',
              }}
            >
              {connectionString}
            </div>
            <CopyButton text={connectionString} />
          </div>
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
          No active WhatsApp subscription.
        </p>
      )}
    </SubscriptionCard>
  );
}

function StatItem({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: string;
  color: string;
}) {
  return (
    <div
      className="rounded-xl p-2.5"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span
          className="w-4 h-4 rounded flex items-center justify-center text-[9px]"
          style={{ backgroundColor: `${color}20`, color }}
        >
          {icon}
        </span>
        <div className="text-[10px]" style={{ color: 'var(--text-dim)' }}>
          {label}
        </div>
      </div>
      <div className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="animate-shimmer rounded-2xl h-32 mb-3" />
  );
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(value < 10 ? 2 : 1)} ${units[i]}`;
}
