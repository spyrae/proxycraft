import { useState, useCallback } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

interface Props {
  text: string;
}

export function CopyButton({ text }: Props) {
  const [copied, setCopied] = useState(false);
  const { t } = useLanguage();

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    setCopied(true);
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      }
    } catch {}
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl transition-all duration-200"
      style={{
        backgroundColor: copied ? 'rgba(16, 185, 129, 0.15)' : 'rgba(16, 185, 129, 0.1)',
        color: '#10B981',
        border: copied ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid transparent',
      }}
    >
      {copied ? (
        <>
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            style={{ animation: 'check-bounce 0.3s ease-out' }}
          >
            <path d="M4 8l3 3 5-5" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {t('copied')}
        </>
      ) : (
        <>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="5" y="5" width="9" height="9" rx="1.5" />
            <path d="M11 5V3.5A1.5 1.5 0 009.5 2h-6A1.5 1.5 0 002 3.5v6A1.5 1.5 0 003.5 11H5" />
          </svg>
          {t('copy')}
        </>
      )}
    </button>
  );
}

