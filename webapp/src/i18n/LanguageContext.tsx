import { createContext, useContext, useState, type ReactNode } from 'react';
import translations, { type Lang, type TranslationKey } from './translations';

function detectInitialLanguage(): Lang {
  const saved = localStorage.getItem('proxycraft_lang');
  if (saved === 'en' || saved === 'ru') return saved;
  try {
    const tgLang = (window as unknown as { Telegram?: { WebApp?: { initDataUnsafe?: { user?: { language_code?: string } } } } })
      .Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
    if (typeof tgLang === 'string' && tgLang.toLowerCase().startsWith('ru')) return 'ru';
  } catch {}
  return 'en';
}

interface LanguageContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectInitialLanguage);

  const setLang = (l: Lang) => {
    localStorage.setItem('proxycraft_lang', l);
    setLangState(l);
  };

  const t = (key: TranslationKey, vars?: Record<string, string | number>): string => {
    let str: string = translations[lang][key];
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        str = str.replace(`{${k}}`, String(v));
      }
    }
    return str;
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
}
