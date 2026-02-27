import type { ReactNode } from 'react';

interface Props {
  title: string;
  status: 'active' | 'expired' | 'none';
  children?: ReactNode;
}

const statusConfig = {
  active: { label: 'Active', color: '#34c759' },
  expired: { label: 'Expired', color: '#ff3b30' },
  none: { label: 'No subscription', color: 'var(--text-hint)' },
};

export function SubscriptionCard({ title, status, children }: Props) {
  const cfg = statusConfig[status];

  return (
    <div
      className="rounded-xl p-4 mb-3"
      style={{ backgroundColor: 'var(--section-bg)' }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h3>
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full"
          style={{ color: cfg.color, backgroundColor: `${cfg.color}18` }}
        >
          {cfg.label}
        </span>
      </div>
      {children}
    </div>
  );
}
