import { useState } from 'react';
import { openLink } from '@telegram-apps/sdk';
import { StatusOverlay } from '../components/StatusOverlay';
import type { OverlayMode } from '../components/StatusOverlay';
import {
  useMe,
  useVpnSubscription,
  useMtprotoSubscription,
  useWhatsappSubscription,
  useCancelSubscription,
  useChangeVpnProfile,
} from '../api/hooks';
import { SubscriptionCard } from '../components/SubscriptionCard';
import { QRCode } from '../components/QRCode';
import { CopyButton } from '../components/CopyButton';
import { useLanguage } from '../i18n/LanguageContext';
import type { TranslationKey } from '../i18n/translations';
import type {
  VpnProfileOption,
  VpnSubscription,
  MtprotoSubscription,
  WhatsappSubscription,
} from '../api/types';

const LOCATION_KEYS: Record<string, TranslationKey> = {
  'Amsterdam': 'loc_amsterdam',
  'Saint Petersburg': 'loc_saint_petersburg',
};

function useLocationLabel(location: string | null | undefined): string | undefined {
  const { t } = useLanguage();
  if (!location) return undefined;
  const key = LOCATION_KEYS[location];
  return key ? t(key) : location;
}

export function MyVpnPage() {
  const { data: me } = useMe();
  const { t } = useLanguage();

  const { data: vpnSub, isLoading: vpnLoading } = useVpnSubscription();
  const { data: mtprotoSub, isLoading: mtprotoLoading } = useMtprotoSubscription();
  const { data: whatsappSub, isLoading: whatsappLoading } = useWhatsappSubscription();

  const mtprotoEnabled = me?.features.mtproto_enabled ?? false;
  const whatsappEnabled = me?.features.whatsapp_enabled ?? false;

  const isLoading = vpnLoading
    || (mtprotoEnabled && mtprotoLoading)
    || (whatsappEnabled && whatsappLoading);

  const showVpn = !!(vpnSub && (vpnSub.active || vpnSub.expired));
  const showMtproto = !!(mtprotoEnabled && mtprotoSub && (mtprotoSub.active || mtprotoSub.expired));
  const showWhatsapp = !!(whatsappEnabled && whatsappSub && (whatsappSub.active || whatsappSub.expired));
  const hasAnything = showVpn || showMtproto || showWhatsapp;

  return (
    <div className="animate-fade-in">
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        {t('my_vpn')}
      </h1>

      {isLoading && (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      )}

      {!isLoading && !hasAnything && <EmptyState />}

      {showVpn && <VpnSection sub={vpnSub!} />}
      {showMtproto && <MtprotoSection sub={mtprotoSub!} />}
      {showWhatsapp && <WhatsappSection sub={whatsappSub!} />}
    </div>
  );
}

function EmptyState() {
  const { t } = useLanguage();
  return (
    <div
      className="rounded-2xl p-8 text-center"
      style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="text-3xl mb-3">🔒</div>
      <p className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
        {t('no_subscriptions_yet')}
      </p>
    </div>
  );
}

function ExpiryBadge({ date }: { date: string }) {
  const { t } = useLanguage();
  return (
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
      {t('expires_date', { date })}
    </div>
  );
}

function CancelButton({
  product,
  cancelledAt,
  expiryDate,
  onCancelled,
}: {
  product: 'vpn' | 'mtproto' | 'whatsapp';
  cancelledAt?: string | null;
  expiryDate?: string;
  onCancelled?: () => void;
}) {
  const { t } = useLanguage();
  const cancel = useCancelSubscription();
  const [confirming, setConfirming] = useState(false);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('hidden');

  if (cancelledAt) {
    return (
      <div
        className="text-xs px-3 py-2 rounded-xl text-center"
        style={{
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          color: '#EF4444',
          border: '1px solid rgba(239, 68, 68, 0.2)',
        }}
      >
        {expiryDate ? t('cancelled_until', { date: expiryDate }) : t('cancelling')}
      </div>
    );
  }

  if (confirming) {
    return (
      <div
        className="rounded-xl p-3 space-y-2"
        style={{
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
        }}
      >
        <p className="text-xs text-center" style={{ color: 'var(--text-muted)' }}>
          {t('cancel_confirm')}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setConfirming(false)}
            className="flex-1 rounded-xl py-2 text-xs font-semibold transition-all"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border)',
            }}
          >
            {t('cancel_confirm_no')}
          </button>
          <button
            onClick={() => {
              setOverlayMode('loading');
              cancel.mutate(
                { product },
                {
                  onSuccess: () => {
                    setOverlayMode('hidden');
                    setConfirming(false);
                    onCancelled?.();
                  },
                  onError: () => setOverlayMode('hidden'),
                },
              );
            }}
            disabled={cancel.isPending}
            className="flex-1 rounded-xl py-2 text-xs font-semibold transition-all"
            style={{
              backgroundColor: '#EF4444',
              color: '#ffffff',
            }}
          >
            {t('cancel_confirm_yes')}
          </button>
          <StatusOverlay mode={overlayMode} loadingKey="cancelling" />
        </div>
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="w-full text-xs py-2 rounded-xl transition-all"
      style={{
        color: '#EF4444',
        backgroundColor: 'rgba(239, 68, 68, 0.08)',
        border: '1px solid rgba(239, 68, 68, 0.15)',
      }}
    >
      {t('cancel_sub')}
    </button>
  );
}

function ExpandToggle({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) {
  const { t } = useLanguage();
  return (
    <button
      onClick={onToggle}
      className="text-[11px] font-semibold px-2.5 py-1 rounded-full transition-all"
      style={{
        backgroundColor: 'rgba(107, 114, 128, 0.15)',
        color: 'var(--text-dim)',
      }}
    >
      {expanded ? t('hide_details') : t('show_details')}
    </button>
  );
}

function ConnectionRow({ value, onOpen }: { value: string; onOpen?: () => void }) {
  const { t } = useLanguage();
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 min-w-0">
        <div
          className="flex-1 min-w-0 text-[11px] font-mono p-2.5 rounded-xl overflow-hidden text-ellipsis whitespace-nowrap"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          }}
        >
          {value}
        </div>
        <CopyButton text={value} />
      </div>
      {onOpen && (
        <button
          onClick={onOpen}
          className="w-full rounded-xl py-2.5 text-sm font-semibold flex items-center justify-center gap-2 transition-all"
          style={{
            backgroundColor: 'rgba(51, 144, 236, 0.15)',
            color: '#3390EC',
            border: '1px solid rgba(51, 144, 236, 0.3)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
          {t('apply_in_tg')}
        </button>
      )}
    </div>
  );
}

function VpnProfileSelector({
  currentProfile,
  profiles,
}: {
  currentProfile?: VpnProfileOption | null;
  profiles?: VpnProfileOption[];
}) {
  const { t } = useLanguage();
  const changeProfile = useChangeVpnProfile();
  const [error, setError] = useState<string | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('hidden');

  const availableProfiles = profiles ?? [];
  const activeSlug = currentProfile?.slug ?? availableProfiles[0]?.slug ?? null;
  const isSwitchable = availableProfiles.length > 1;

  if (availableProfiles.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2.5">
      <StatusOverlay mode={overlayMode} loadingKey="switching_profile" />

      <div className="space-y-1">
        <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
          {t('connection_profile')}
        </p>
        {isSwitchable && (
          <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>
            {t('connection_profile_hint')}
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {availableProfiles.map((profile) => {
          const isActive = profile.slug === activeSlug;
          return (
            <button
              key={profile.slug}
              type="button"
              disabled={!isSwitchable || changeProfile.isPending}
              onClick={() => {
                if (!isSwitchable || isActive) return;
                setError(null);
                setOverlayMode('loading');
                changeProfile.mutate(
                  { profileSlug: profile.slug },
                  {
                    onSuccess: () => {
                      setError(null);
                      setOverlayMode('hidden');
                    },
                    onError: () => {
                      setOverlayMode('hidden');
                      setError(t('connection_profile_failed'));
                    },
                  },
                );
              }}
              className="px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 disabled:opacity-100"
              style={{
                backgroundColor: isActive ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-card)',
                color: isActive ? '#10B981' : 'var(--text-dim)',
                border: isActive
                  ? '1px solid rgba(16, 185, 129, 0.35)'
                  : '1px solid var(--border)',
              }}
            >
              <span className="flex items-center gap-2">
                <span>{profile.emoji}</span>
                <span>{profile.name}</span>
              </span>
            </button>
          );
        })}
      </div>

      {error && (
        <p className="text-[11px]" style={{ color: '#EF4444' }}>
          {error}
        </p>
      )}
    </div>
  );
}

function VpnSection({ sub }: { sub: VpnSubscription }) {
  const { t } = useLanguage();
  const locationLabel = useLocationLabel(sub.location);
  const [expanded, setExpanded] = useState(false);
  const [wasJustCancelled, setWasJustCancelled] = useState(false);

  const effectiveCancelled = wasJustCancelled || !!sub.cancelled_at;
  const status = effectiveCancelled ? (sub.active ? 'cancelled' : 'expired') : (sub.active ? 'active' : 'expired');

  return (
    <SubscriptionCard
      title="VPN"
      status={status}
      location={locationLabel}
      action={sub.active ? <ExpandToggle expanded={expanded} onToggle={() => setExpanded(!expanded)} /> : undefined}
    >
      {sub.active && (
        <div className="space-y-3">
          {sub.expiry_time && sub.expiry_time > 0 && (
            <ExpiryBadge date={new Date(sub.expiry_time).toLocaleDateString()} />
          )}

          {expanded && (
            <>
              <VpnProfileSelector
                currentProfile={sub.current_profile}
                profiles={sub.available_profiles}
              />

              <div className="grid grid-cols-2 gap-2">
                <StatItem label={t('upload')} value={formatBytes(sub.traffic_up || 0)} icon="↑" color="#06B6D4" />
                <StatItem label={t('download')} value={formatBytes(sub.traffic_down || 0)} icon="↓" color="#10B981" />
                <StatItem label={t('total_used')} value={formatBytes(sub.traffic_used || 0)} icon="◎" color="#8B5CF6" />
                <StatItem label={t('devices')} value={sub.max_devices === -1 ? '∞' : String(sub.max_devices)} icon="⊞" color="#F59E0B" />
              </div>

              {sub.key && (
                <div className="space-y-3">
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                    {t('connection_key')}
                  </p>
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className="flex-1 min-w-0 text-[11px] font-mono p-2.5 rounded-xl overflow-hidden text-ellipsis whitespace-nowrap"
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

              <CancelButton
                product="vpn"
                cancelledAt={effectiveCancelled ? (sub.cancelled_at || 'local') : null}
                expiryDate={sub.expiry_time ? new Date(sub.expiry_time).toLocaleDateString() : undefined}
                onCancelled={() => setWasJustCancelled(true)}
              />
            </>
          )}
        </div>
      )}

      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {t('expired_sub')}
        </p>
      )}
    </SubscriptionCard>
  );
}

function MtprotoSection({ sub }: { sub: MtprotoSubscription }) {
  const { t } = useLanguage();
  const locationLabel = useLocationLabel(sub.location);
  const [expanded, setExpanded] = useState(false);
  const [wasJustCancelled, setWasJustCancelled] = useState(false);

  const effectiveCancelled = wasJustCancelled || !!sub.cancelled_at;
  const status = effectiveCancelled ? (sub.active ? 'cancelled' : 'expired') : (sub.active ? 'active' : 'expired');

  return (
    <SubscriptionCard
      title="Telegram Proxy"
      status={status}
      location={locationLabel}
      action={sub.active ? <ExpandToggle expanded={expanded} onToggle={() => setExpanded(!expanded)} /> : undefined}
    >
      {sub.active && (
        <div className="space-y-3">
          {sub.expires_at && (
            <ExpiryBadge date={new Date(sub.expires_at).toLocaleDateString()} />
          )}
          {expanded && (
            <>
              {sub.link && (
                <ConnectionRow
                  value={sub.link}
                  onOpen={() => openLink(sub.link!)}
                />
              )}
              <CancelButton
                product="mtproto"
                cancelledAt={effectiveCancelled ? (sub.cancelled_at || 'local') : null}
                expiryDate={sub.expires_at ? new Date(sub.expires_at).toLocaleDateString() : undefined}
                onCancelled={() => setWasJustCancelled(true)}
              />
            </>
          )}
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {t('expired_sub')}
        </p>
      )}
    </SubscriptionCard>
  );
}

function WhatsappSection({ sub }: { sub: WhatsappSubscription }) {
  const { t } = useLanguage();
  const locationLabel = useLocationLabel(sub.location);
  const [expanded, setExpanded] = useState(false);
  const [wasJustCancelled, setWasJustCancelled] = useState(false);

  const effectiveCancelled = wasJustCancelled || !!sub.cancelled_at;
  const status = effectiveCancelled ? (sub.active ? 'cancelled' : 'expired') : (sub.active ? 'active' : 'expired');
  const connectionString = sub.host && sub.port ? `${sub.host}:${sub.port}` : null;

  return (
    <SubscriptionCard
      title="WhatsApp Proxy"
      status={status}
      location={locationLabel}
      action={sub.active ? <ExpandToggle expanded={expanded} onToggle={() => setExpanded(!expanded)} /> : undefined}
    >
      {sub.active && (
        <div className="space-y-3">
          {sub.expires_at && (
            <ExpiryBadge date={new Date(sub.expires_at).toLocaleDateString()} />
          )}
          {expanded && (
            <>
              {connectionString && <ConnectionRow value={connectionString} />}
              <CancelButton
                product="whatsapp"
                cancelledAt={effectiveCancelled ? (sub.cancelled_at || 'local') : null}
                expiryDate={sub.expires_at ? new Date(sub.expires_at).toLocaleDateString() : undefined}
                onCancelled={() => setWasJustCancelled(true)}
              />
            </>
          )}
        </div>
      )}
      {!sub.active && (
        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {t('expired_sub')}
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
        backgroundColor: 'var(--bg-card)',
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
