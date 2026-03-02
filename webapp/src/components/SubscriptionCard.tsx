import type { ReactNode } from 'react';

interface Props {
  title: string;
  status: 'active' | 'expired' | 'none';
  children?: ReactNode;
}

const statusConfig = {
  active: { label: 'Active', color: '#10B981', bg: 'rgba(16, 185, 129, 0.12)' },
  expired: { label: 'Expired', color: '#EF4444', bg: 'rgba(239, 68, 68, 0.12)' },
  none: { label: 'No subscription', color: '#6B7280', bg: 'rgba(107, 114, 128, 0.12)' },
};

export function SubscriptionCard({ title, status, children }: Props) {
  const cfg = statusConfig[status];

  return (
    <div
      className="card-gradient-border p-4 mb-3 animate-fade-in"
      style={{
        borderColor: status === 'active' ? 'rgba(16, 185, 129, 0.2)' : undefined,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: cfg.color,
              boxShadow: status === 'active' ? `0 0 8px ${cfg.color}` : 'none',
            }}
          />
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            {title}
          </h3>
        </div>
        <span
          className="text-[11px] font-semibold px-2.5 py-1 rounded-full"
          style={{ color: cfg.color, backgroundColor: cfg.bg }}
        >
          {cfg.label}
        </span>
      </div>
      {children}
    </div>
  );
}
