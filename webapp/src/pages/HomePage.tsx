import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTelegram } from '../hooks/useTelegram';
import { useMe, useVpnSubscription } from '../api/hooks';
import { TopupModal } from '../components/TopupModal';
import { createPortal } from 'react-dom';
import { useLanguage } from '../i18n/LanguageContext';
import type { TranslationKey } from '../i18n/translations';

export function HomePage() {
  const { user } = useTelegram();
  const { data: me, isLoading, error } = useMe();
  const { t } = useLanguage();

  if (isLoading) return <HomeLoading />;
  if (error || !me) return <HomeError />;

  const hasActiveVpn = me.subscriptions.vpn.active;

  return (
    <div className="animate-fade-in">
      {/* Greeting + Language toggle + Protected badge */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('greeting', { name: user?.first_name || me.first_name })}
        </p>
        <div className="flex items-center gap-2">
          <LangToggle />
          <ProtectedBadge active={hasActiveVpn} />
        </div>
      </div>

      {/* Balance Card */}
      <BalanceCard balance={me.balance} />

      {/* Stats or Quick Setup */}
      {hasActiveVpn ? <ActiveStats /> : <QuickSetup me={me} />}

      {/* Setup Guides */}
      <SetupGuides />

      {/* Help / FAQ */}
      <HelpFaq />
    </div>
  );
}

function LangToggle() {
  const { lang, setLang } = useLanguage();
  const nextLang = lang === 'en' ? 'ru' : 'en';
  return (
    <button
      onClick={() => setLang(nextLang)}
      className="text-[11px] font-bold px-2 py-1 rounded-full"
      style={{
        backgroundColor: 'rgba(107, 114, 128, 0.12)',
        color: 'var(--text-dim)',
        border: '1px solid var(--border)',
      }}
    >
      {nextLang.toUpperCase()}
    </button>
  );
}

function ProtectedBadge({ active }: { active: boolean }) {
  const { t } = useLanguage();
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[11px] font-bold"
      style={{
        backgroundColor: active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(127, 29, 29, 0.2)',
        color: active ? '#10B981' : '#9B2C2C',
        border: `1px solid ${active ? 'rgba(16, 185, 129, 0.4)' : 'rgba(127, 29, 29, 0.4)'}`,
        boxShadow: active ? '0 0 10px rgba(16, 185, 129, 0.2)' : '0 0 8px rgba(127, 29, 29, 0.1)',
      }}
    >
      <img
        src="/favicon.svg?v=2"
        width="14"
        height="14"
        alt=""
        style={{ opacity: active ? 1 : 0.5 }}
      />
      {active ? t('protected') : t('unprotected')}
    </div>
  );
}

function BalanceCard({ balance }: { balance: number }) {
  const [showTopup, setShowTopup] = useState(false);
  const { t } = useLanguage();

  return (
    <>
      <div className="card-gradient-border p-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
              {t('balance_label')}
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
      </div>

      {showTopup && <TopupModal onClose={() => setShowTopup(false)} />}
    </>
  );
}

function ActiveStats() {
  const { data: sub, isLoading } = useVpnSubscription();
  const { t } = useLanguage();

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

  const progressPercent = sub.expiry_time
    ? Math.min(100, Math.max(0, (daysLeft / 30) * 100))
    : 0;

  return (
    <div className="space-y-3 animate-slide-up">
      {sub.expiry_time && sub.expiry_time > 0 && (
        <div className="card-gradient-border p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              {t('subscription')}
            </span>
            <span
              className="text-xs font-bold"
              style={{ color: daysLeft <= 3 ? 'var(--danger)' : '#10B981' }}
            >
              {t('days_left', { n: daysLeft })}
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
            {t('expires_date', { date: new Date(sub.expiry_time).toLocaleDateString() })}
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <StatCard icon="↑" label={t('upload')} value={formatBytes(sub.traffic_up || 0)} color="#06B6D4" />
        <StatCard icon="↓" label={t('download')} value={formatBytes(sub.traffic_down || 0)} color="#10B981" />
        <StatCard icon="◎" label={t('total_used')} value={formatBytes(sub.traffic_used || 0)} color="#8B5CF6" />
        <StatCard icon="⊞" label={t('devices')} value={sub.max_devices === -1 ? '∞' : String(sub.max_devices || 0)} color="#F59E0B" />
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
  const { t } = useLanguage();

  const steps = [
    {
      num: '1',
      title: t('step1_title'),
      desc: t('step1_desc'),
      action: undefined as (() => void) | undefined,
      color: '#F59E0B',
    },
    {
      num: '2',
      title: t('step2_title'),
      desc: t('step2_desc'),
      action: () => navigate('/plans'),
      color: '#10B981',
    },
    {
      num: '3',
      title: t('step3_title'),
      desc: t('step3_desc'),
      color: '#8B5CF6',
    },
  ];

  return (
    <div className="space-y-3 animate-slide-up">
      <h2 className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>
        {t('get_started')}
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
            {t('free_trial_available')}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
            {t('no_payment_required')}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Setup Guides ──────────────────────────────────────────────────────────────

type GuideId = 'vpn' | 'telegram' | 'whatsapp';

const GUIDE_DEFS: { id: GuideId; color: string; icon: React.ReactElement }[] = [
  {
    id: 'vpn',
    color: '#10B981',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    id: 'telegram',
    color: '#3390EC',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="22" y1="2" x2="11" y2="13" />
        <polygon points="22 2 15 22 11 13 2 9 22 2" />
      </svg>
    ),
  },
  {
    id: 'whatsapp',
    color: '#25D366',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
        <path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.122 1.528 5.855L.057 23.882l6.198-1.624A11.93 11.93 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.793 9.793 0 01-5.017-1.378l-.36-.213-3.681.965.981-3.593-.234-.369A9.794 9.794 0 012.182 12C2.182 6.57 6.57 2.182 12 2.182c5.43 0 9.818 4.388 9.818 9.818 0 5.43-4.388 9.818-9.818 9.818z" />
      </svg>
    ),
  },
];

function SetupGuides() {
  const [openGuide, setOpenGuide] = useState<GuideId | null>(null);
  const { t } = useLanguage();

  const guides = GUIDE_DEFS.map((g) => ({
    ...g,
    title: t(`guide_${g.id}_title` as TranslationKey),
    desc: t(`guide_${g.id}_desc` as TranslationKey),
    content: t(`guide_${g.id}_content` as TranslationKey),
  }));

  const guide = guides.find((g) => g.id === openGuide);

  return (
    <>
      <div className="mt-4 space-y-2">
        <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
          {t('setup_guides')}
        </p>
        {guides.map((g) => (
          <button
            key={g.id}
            onClick={() => setOpenGuide(g.id)}
            className="w-full card-gradient-border p-3.5 flex items-center gap-3 text-left transition-all"
          >
            <span
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${g.color}20`, color: g.color }}
            >
              {g.icon}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {g.title}
              </p>
              <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-dim)' }}>
                {g.desc}
              </p>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-dim)', flexShrink: 0 }}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        ))}
      </div>

      {guide && (
        <GuideSheet
          title={guide.title}
          color={guide.color}
          content={guide.content}
          onClose={() => setOpenGuide(null)}
        />
      )}
    </>
  );
}

function GuideSheet({ title, color, content, onClose }: {
  title: string;
  color: string;
  content: string;
  onClose: () => void;
}) {
  const { t } = useLanguage();
  return createPortal(
    <>
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 9000, backgroundColor: 'rgba(0,0,0,0.5)' }}
        onClick={onClose}
      />
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 9001,
          borderRadius: '24px 24px 0 0',
          backgroundColor: 'var(--bg-primary)',
          maxHeight: '80vh',
          overflowY: 'auto',
          animation: 'sheet-up 0.3s ease-out',
        }}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full" style={{ backgroundColor: 'var(--border)' }} />
        </div>

        <div className="px-6 pb-10 pt-3">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              {title}
            </h2>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-dim)' }}
            >
              ✕
            </button>
          </div>

          {/* Placeholder */}
          <div
            className="rounded-2xl p-5 text-center"
            style={{ backgroundColor: 'var(--bg-card)', border: `1px dashed ${color}40` }}
          >
            <p className="text-sm font-semibold mb-1" style={{ color }}>
              {t('coming_soon')}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
              {content}
            </p>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}

// ── Help / FAQ ─────────────────────────────────────────────────────────────────

function HelpFaq() {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const { t } = useLanguage();

  const FAQ_ITEMS = [
    { q: t('faq1_q'), a: t('faq1_a') },
    { q: t('faq2_q'), a: t('faq2_a') },
    { q: t('faq3_q'), a: t('faq3_a') },
    { q: t('faq4_q'), a: t('faq4_a') },
    { q: t('faq5_q'), a: t('faq5_a') },
  ];

  return (
    <div className="mt-4 mb-2">
      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
        {t('help_faq')}
      </p>
      <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        {FAQ_ITEMS.map((item, idx) => {
          const isOpen = openIdx === idx;
          const isLast = idx === FAQ_ITEMS.length - 1;
          return (
            <div key={idx} style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)' }}>
              <button
                onClick={() => setOpenIdx(isOpen ? null : idx)}
                className="w-full flex items-center justify-between px-4 py-3.5 text-left transition-colors"
                style={{ backgroundColor: isOpen ? 'var(--bg-card-hover)' : 'var(--bg-card)' }}
              >
                <span className="text-sm font-medium pr-3" style={{ color: 'var(--text-primary)' }}>
                  {item.q}
                </span>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    color: 'var(--text-dim)',
                    flexShrink: 0,
                    transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease',
                  }}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {isOpen && (
                <div
                  className="px-4 pb-4 text-sm"
                  style={{ color: 'var(--text-muted)', backgroundColor: 'var(--bg-card)' }}
                >
                  {item.a}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Home loading / error ───────────────────────────────────────────────────────

function HomeLoading() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="animate-shimmer rounded-xl h-5 w-28" />
        <div className="animate-shimmer rounded-full h-7 w-24" />
      </div>
      <div className="animate-shimmer rounded-2xl h-16" />
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="animate-shimmer rounded-2xl h-20" />
        ))}
      </div>
    </div>
  );
}

function HomeError() {
  const { t } = useLanguage();
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
        {t('failed_load')}
      </p>
      <button
        onClick={() => window.location.reload()}
        className="text-sm font-semibold px-5 py-2.5 rounded-xl transition-all"
        style={{
          backgroundColor: '#10B981',
          color: '#ffffff',
        }}
      >
        {t('retry')}
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
