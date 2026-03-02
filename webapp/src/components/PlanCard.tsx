interface Props {
  title: string;
  description: string;
  price: number | string;
  currency?: string;
  selected?: boolean;
  popular?: boolean;
  onSelect: () => void;
}

export function PlanCard({
  title,
  description,
  price,
  currency = '★',
  selected,
  popular,
  onSelect,
}: Props) {
  return (
    <button
      onClick={onSelect}
      className="w-full rounded-2xl p-4 mb-2 text-left transition-all duration-200 relative"
      style={{
        backgroundColor: selected ? 'var(--bg-card-hover)' : 'var(--bg-card)',
        border: selected ? '2px solid #10B981' : '2px solid var(--border)',
        boxShadow: selected ? '0 0 20px rgba(16, 185, 129, 0.15)' : 'none',
      }}
    >
      {popular && (
        <span
          className="absolute -top-2.5 right-3 text-[10px] font-bold px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: '#10B981',
            color: '#ffffff',
            boxShadow: '0 2px 8px rgba(16, 185, 129, 0.4)',
          }}
        >
          Popular
        </span>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Selection indicator */}
          <div
            className="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all duration-200"
            style={{
              borderColor: selected ? '#10B981' : '#4B5563',
              backgroundColor: selected ? '#10B981' : 'transparent',
            }}
          >
            {selected && (
              <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                <path d="M3 6l2 2 4-4" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {title}
            </p>
            {description && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
                {description}
              </p>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <span className="text-lg font-bold" style={{ color: selected ? '#10B981' : 'var(--text-primary)' }}>
            {price}
          </span>
          <span className="text-xs ml-1" style={{ color: 'var(--text-dim)' }}>
            {currency}
          </span>
        </div>
      </div>
    </button>
  );
}
