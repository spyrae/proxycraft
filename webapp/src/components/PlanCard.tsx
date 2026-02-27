interface Props {
  title: string;
  description: string;
  price: number | string;
  currency?: string;
  selected?: boolean;
  onSelect: () => void;
}

export function PlanCard({ title, description, price, currency = '★', selected, onSelect }: Props) {
  return (
    <button
      onClick={onSelect}
      className="w-full rounded-xl p-4 mb-2 text-left transition-all"
      style={{
        backgroundColor: 'var(--section-bg)',
        border: selected ? '2px solid var(--accent)' : '2px solid transparent',
      }}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {title}
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-hint)' }}>
            {description}
          </p>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold" style={{ color: 'var(--accent)' }}>
            {price}
          </span>
          <span className="text-xs ml-1" style={{ color: 'var(--text-hint)' }}>
            {currency}
          </span>
        </div>
      </div>
    </button>
  );
}
