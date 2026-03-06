import type { ReactNode } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

interface Props {
  title: string;
  status: 'active' | 'expired' | 'none';
  location?: string | null;
  children?: ReactNode;
}

export function SubscriptionCard({ title, status, location, children }: Props) {
  const { t } = useLanguage();

  const statusConfig = {
    active: { label: t('status_active'), color: '#10B981', bg: 'rgba(16, 185, 129, 0.12)' },
    expired: { label: t('status_expired'), color: '#EF4444', bg: 'rgba(239, 68, 68, 0.12)' },
    none: { label: t('status_none'), color: '#6B7280', bg: 'rgba(107, 114, 128, 0.12)' },
  };

  const cfg = statusConfig[status];

  return (
    <div
      className="card-gradient-border p-4 mb-3 animate-fade-in"
      style={{
        borderColor: status === 'active' ? 'rgba(16, 185, 129, 0.2)' : undefined,
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-start gap-2">
          <div
            className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
            style={{
              backgroundColor: cfg.color,
              boxShadow: status === 'active' ? `0 0 8px ${cfg.color}` : 'none',
            }}
          />
          <div>
            <h3 className="text-base font-semibold leading-tight" style={{ color: 'var(--text-primary)' }}>
              {title}
            </h3>
            {location && (
              <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
                📍 {location}
              </p>
            )}
          </div>
        </div>
        <span
          className="text-[11px] font-semibold px-2.5 py-1 rounded-full flex-shrink-0 ml-2"
          style={{ color: cfg.color, backgroundColor: cfg.bg }}
        >
          {cfg.label}
        </span>
      </div>
      {children}
    </div>
  );
}
