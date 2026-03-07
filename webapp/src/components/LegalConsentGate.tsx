import { openLink } from '@telegram-apps/sdk';
import { useMemo, useState } from 'react';
import { useAcceptLegalConsents } from '../api/hooks';
import { StatusOverlay } from './StatusOverlay';
import { useLanguage } from '../i18n/LanguageContext';

const SITE_BASE_URL = 'https://proxycraft.tech';

function getDocumentUrls(lang: 'en' | 'ru') {
  const base = lang === 'ru' ? SITE_BASE_URL : `${SITE_BASE_URL}/en`;
  return {
    privacy: `${base}/privacy`,
    terms: `${base}/terms`,
    personalData: `${base}/personal-data-consent`,
  };
}

type ConsentState = {
  privacy: boolean;
  terms: boolean;
  personalData: boolean;
  marketing: boolean;
};

function openDocument(url: string) {
  try {
    openLink(url, { tryBrowser: 'chrome' });
  } catch {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

export function LegalConsentGate() {
  const { lang, setLang, t } = useLanguage();
  const acceptConsents = useAcceptLegalConsents();
  const documentUrls = useMemo(() => getDocumentUrls(lang), [lang]);
  const [consents, setConsents] = useState<ConsentState>({
    privacy: false,
    terms: false,
    personalData: false,
    marketing: false,
  });

  const requiredAccepted = consents.privacy && consents.terms && consents.personalData;

  const toggle = (key: keyof ConsentState) => {
    setConsents((previous) => ({ ...previous, [key]: !previous[key] }));
  };

  const selectAll = () => {
    setConsents({
      privacy: true,
      terms: true,
      personalData: true,
      marketing: true,
    });
  };

  return (
    <div className="min-h-[100dvh] px-4 py-4 flex items-center justify-center">
      <StatusOverlay mode={acceptConsents.isPending ? 'loading' : 'hidden'} loadingKey="saving_consents" />
      <div
        className="w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-[24px] p-4 md:p-5"
        style={{
          background: 'linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(10, 14, 23, 0.98))',
          border: '1px solid rgba(52, 211, 153, 0.16)',
          boxShadow: '0 24px 80px rgba(0, 0, 0, 0.45)',
        }}
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            <div
              className="w-10 h-10 rounded-2xl flex items-center justify-center mb-2"
              style={{
                background: 'radial-gradient(circle at 30% 30%, rgba(52, 211, 153, 0.22), rgba(17, 24, 39, 0.88))',
                border: '1px solid rgba(52, 211, 153, 0.22)',
              }}
            >
              <img src="/favicon.svg?v=2" alt="" className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
              {t('consent_title')}
            </h1>
            <p className="text-sm leading-5" style={{ color: 'var(--text-muted)' }}>
              {t('consent_subtitle')}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setLang(lang === 'en' ? 'ru' : 'en')}
            className="shrink-0 text-[11px] font-bold px-3 py-2 rounded-full"
            style={{
              backgroundColor: 'rgba(107, 114, 128, 0.12)',
              color: 'var(--text-dim)',
              border: '1px solid var(--border)',
            }}
          >
            {(lang === 'en' ? 'ru' : 'en').toUpperCase()}
          </button>
        </div>

        <div className="space-y-2.5">
          <ConsentRow
            checked={consents.privacy}
            required
            label={t('consent_privacy_label')}
            tagLabel={t('consent_required')}
            onToggle={() => toggle('privacy')}
            onOpen={() => openDocument(documentUrls.privacy)}
            openLabel={t('consent_open_document')}
          />
          <ConsentRow
            checked={consents.terms}
            required
            label={t('consent_terms_label')}
            tagLabel={t('consent_required')}
            onToggle={() => toggle('terms')}
            onOpen={() => openDocument(documentUrls.terms)}
            openLabel={t('consent_open_document')}
          />
          <ConsentRow
            checked={consents.personalData}
            required
            label={t('consent_personal_data_label')}
            tagLabel={t('consent_required')}
            onToggle={() => toggle('personalData')}
            onOpen={() => openDocument(documentUrls.personalData)}
            openLabel={t('consent_open_document')}
          />
          <ConsentRow
            checked={consents.marketing}
            required={false}
            label={t('consent_marketing_label')}
            tagLabel={t('consent_optional')}
            onToggle={() => toggle('marketing')}
          />
        </div>

        {acceptConsents.isError && (
          <div
            className="mt-4 rounded-2xl px-4 py-3 text-sm"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.08)',
              color: '#FCA5A5',
              border: '1px solid rgba(239, 68, 68, 0.18)',
            }}
          >
            {t('consent_error_body')}
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={selectAll}
            className="w-full min-h-11 px-5 py-3 rounded-2xl text-sm font-semibold leading-none sm:w-auto"
            style={{
              backgroundColor: 'rgba(17, 24, 39, 0.96)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
            }}
          >
            {t('consent_select_all')}
          </button>

          <button
            type="button"
            onClick={() => {
              if (!requiredAccepted) return;
              acceptConsents.mutate({
                privacy_policy: consents.privacy,
                terms_of_use: consents.terms,
                personal_data: consents.personalData,
                marketing: consents.marketing,
              });
            }}
            disabled={!requiredAccepted || acceptConsents.isPending}
            className="w-full min-h-11 flex-1 rounded-2xl px-5 py-3 text-sm font-bold leading-none whitespace-nowrap transition-all"
            style={{
              background: requiredAccepted
                ? 'linear-gradient(90deg, #10B981, #34D399)'
                : 'rgba(31, 41, 55, 0.7)',
              color: requiredAccepted ? '#03130D' : 'var(--text-dim)',
              boxShadow: requiredAccepted ? '0 12px 32px rgba(16, 185, 129, 0.24)' : 'none',
            }}
          >
            {t('consent_continue')}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConsentRow({
  checked,
  required,
  label,
  tagLabel,
  openLabel,
  onToggle,
  onOpen,
}: {
  checked: boolean;
  required: boolean;
  label: string;
  tagLabel: string;
  openLabel?: string;
  onToggle: () => void;
  onOpen?: () => void;
}) {
  return (
    <div
      className="rounded-2xl px-3.5 py-3"
      style={{
        backgroundColor: checked ? 'rgba(16, 185, 129, 0.08)' : 'rgba(17, 24, 39, 0.82)',
        border: `1px solid ${checked ? 'rgba(52, 211, 153, 0.3)' : 'var(--border)'}`,
      }}
    >
      <div className="flex items-start gap-3">
        <button type="button" onClick={onToggle} className="shrink-0 mt-0.5">
        <span
          className="shrink-0 w-5 h-5 rounded-md flex items-center justify-center text-[11px] font-bold"
          style={{
            backgroundColor: checked ? '#10B981' : 'rgba(10, 14, 23, 0.9)',
            border: `1px solid ${checked ? '#34D399' : 'var(--border)'}`,
            color: checked ? '#03130D' : 'transparent',
            boxShadow: checked ? '0 0 0 3px rgba(16, 185, 129, 0.10)' : 'none',
          }}
        >
          ✓
        </span>
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <button
              type="button"
              onClick={onToggle}
              className="min-w-0 flex-1 text-left"
            >
              <span className="block text-sm font-semibold leading-5" style={{ color: 'var(--text-primary)' }}>
                {label}
              </span>
            </button>

            {onOpen && openLabel ? (
              <button
                type="button"
                onClick={onOpen}
                className="shrink-0 text-xs font-semibold underline underline-offset-4"
                style={{ color: 'var(--text-link)' }}
              >
                {openLabel}
              </button>
            ) : null}
          </div>

          <span
            className="inline-flex mt-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold"
            style={{
              backgroundColor: required ? 'rgba(245, 158, 11, 0.14)' : 'rgba(52, 211, 153, 0.12)',
              color: required ? '#FBBF24' : '#6EE7B7',
            }}
          >
            {tagLabel}
          </span>
        </div>
      </div>
    </div>
  );
}
