export interface SubscriptionStatus {
  active: boolean;
  trial_available: boolean;
}

export interface LegalConsents {
  version: string;
  privacy_policy_accepted: boolean;
  terms_of_use_accepted: boolean;
  personal_data_consent_accepted: boolean;
  marketing_consent_granted: boolean;
  required_consents_accepted: boolean;
  accepted_at: {
    privacy_policy: string | null;
    terms_of_use: string | null;
    personal_data: string | null;
    marketing: string | null;
  };
}

export interface UserProfile {
  tg_id: number;
  first_name: string;
  username: string | null;
  created_at: string | null;
  is_admin: boolean;
  balance: number;
  auto_renew: boolean;
  vpn_profile_slug?: string | null;
  legal_consents: LegalConsents;
  subscriptions: {
    vpn: SubscriptionStatus;
    mtproto: SubscriptionStatus;
    whatsapp: SubscriptionStatus;
  };
  features: {
    mtproto_enabled: boolean;
    whatsapp_enabled: boolean;
    stars_enabled: boolean;
  };
}

export interface VpnPlan {
  devices: number;
  prices: Record<string, Record<number, number>>;
  durations: number[];
}

export interface ServicePlan {
  duration: number;
  price_rub: number;
  price_stars: number;
}

export interface VpnProfileOption {
  slug: string;
  name: string;
  name_en?: string;
  emoji: string;
  kind: 'operator' | 'universal' | string;
  order: number;
}

export interface VpnSubscription {
  subscription_id?: number | null;
  active: boolean;
  expired?: boolean;
  max_devices?: number;
  traffic_total?: number;
  traffic_used?: number;
  traffic_up?: number;
  traffic_down?: number;
  traffic_remaining?: number;
  expiry_time?: number;
  key?: string | null;
  location?: string | null;
  cancelled_at?: string | null;
  current_profile?: VpnProfileOption | null;
  available_profiles?: VpnProfileOption[];
}

export interface MtprotoSubscription {
  subscription_id?: number | null;
  active: boolean;
  expired?: boolean;
  expires_at?: string | null;
  link?: string | null;
  location?: string | null;
  cancelled_at?: string | null;
}

export interface WhatsappSubscription {
  subscription_id?: number | null;
  active: boolean;
  expired?: boolean;
  expires_at?: string | null;
  host?: string;
  port?: number;
  location?: string | null;
  cancelled_at?: string | null;
}

export interface CancelSubscriptionResponse {
  success: boolean;
  product: string;
  subscription_id?: number | null;
  expires_at?: string | null;
}

export interface InvoiceResponse {
  invoice_url?: string;
  payment_url?: string;
}

export interface TrialVpnResponse {
  success: boolean;
  key: string | null;
}

export interface TrialMtprotoResponse {
  success: boolean;
  link: string | null;
}

export interface TrialWhatsappResponse {
  success: boolean;
  host: string;
  port: number;
}

export interface PromocodeResponse {
  success: boolean;
  duration: number;
}

export interface TopupResponse {
  invoice_url?: string;
  payment_url?: string;
  stars_amount?: number;
}

export interface BuyPlanResponse {
  success: boolean;
  product: string;
  duration: number;
  vpn_subscription?: VpnSubscription;
  mtproto_subscription?: MtprotoSubscription;
  whatsapp_subscription?: WhatsappSubscription;
}

export interface SubscriptionsResponse {
  vpn: VpnSubscription[];
  mtproto: MtprotoSubscription[];
  whatsapp: WhatsappSubscription[];
}

export type ChangeVpnProfileResponse = VpnSubscription;

export interface AutoRenewResponse {
  auto_renew: boolean;
}

export interface AcceptLegalConsentsResponse {
  legal_consents: LegalConsents;
}

export interface ApiError {
  error: string;
  required?: number;
  balance?: number;
}
