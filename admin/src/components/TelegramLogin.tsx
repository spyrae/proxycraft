import { useEffect, useRef } from 'react';
import type { TelegramLoginData } from '../api/types.ts';

interface TelegramLoginProps {
  botName: string;
  onAuth: (data: TelegramLoginData) => void;
}

export function TelegramLogin({ botName, onAuth }: TelegramLoginProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Expose callback globally for the Telegram widget
    (window as unknown as Record<string, unknown>).__onTelegramAuth = (user: TelegramLoginData) => {
      onAuth(user);
    };

    // Load Telegram Login Widget script
    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.async = true;
    script.setAttribute('data-telegram-login', botName);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-radius', '8');
    script.setAttribute('data-onauth', '__onTelegramAuth(user)');
    script.setAttribute('data-request-access', 'write');

    const container = containerRef.current;
    if (container) {
      container.innerHTML = '';
      container.appendChild(script);
    }

    return () => {
      delete (window as unknown as Record<string, unknown>).__onTelegramAuth;
    };
  }, [botName, onAuth]);

  return <div ref={containerRef} className="flex justify-center" />;
}
