import ru from './ru.json';
import en from './en.json';

type Translations = typeof ru;
type Lang = 'ru' | 'en';

const translations: Record<Lang, Translations> = { ru, en };

export function getLangFromUrl(url: URL): Lang {
  const [, lang] = url.pathname.split('/');
  if (lang === 'en') return 'en';
  return 'ru';
}

export function t(lang: Lang): Translations {
  return translations[lang];
}

export function getLocalePath(lang: Lang, path: string): string {
  if (lang === 'ru') return path;
  return `/en${path}`;
}

export function getAlternateLang(lang: Lang): Lang {
  return lang === 'ru' ? 'en' : 'ru';
}

export function getAlternateUrl(lang: Lang, currentPath: string): string {
  if (lang === 'ru') {
    return `/en${currentPath}`;
  }
  return currentPath.replace(/^\/en/, '') || '/';
}
