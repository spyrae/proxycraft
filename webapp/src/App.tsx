import { useEffect } from 'react';

export default function App({ onReady }: { onReady?: () => void }) {
  useEffect(() => {
    onReady?.();
  }, [onReady]);

  return (
    <div
      className="min-h-[100dvh] flex items-center justify-center px-6"
      style={{ backgroundColor: '#0A0E17' }}
    >
      <div className="max-w-sm w-full text-center">
        <div
          className="w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center"
          style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.2)',
          }}
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#10B981"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h1
          className="text-2xl font-bold mb-3"
          style={{ color: '#F9FAFB', fontFamily: 'Inter, sans-serif' }}
        >
          Сервис приостановлен
        </h1>
        <p
          className="text-base"
          style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif' }}
        >
          Мы проводим технические работы. Приносим извинения за неудобства.
        </p>
      </div>
    </div>
  );
}
