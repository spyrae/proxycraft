"""Serializers: model → JSON-safe dict for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.bot.utils.legal_consents import LEGAL_CONSENTS_VERSION, has_required_legal_consents

if TYPE_CHECKING:
    from app.bot.models import ClientData
    from app.bot.services.product_catalog import Operator, Product, VpnProfile
    from app.db.models import MTProtoSubscription, Server, Transaction, User, WhatsAppSubscription


def serialize_user(
    user: User,
    vpn_active: bool,
    mtproto_active: bool,
    whatsapp_active: bool,
    vpn_trial_available: bool,
    mtproto_trial_available: bool,
    whatsapp_trial_available: bool,
) -> dict:
    return {
        "tg_id": user.tg_id,
        "first_name": user.first_name,
        "username": user.username,
        "operator": user.operator,
        "vpn_profile_slug": user.vpn_profile_slug,
        "legal_consents": serialize_legal_consents(user),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "balance": user.balance / 100,  # kopecks → rubles
        "auto_renew": user.auto_renew,
        "subscriptions": {
            "vpn": {
                "active": vpn_active,
                "trial_available": vpn_trial_available,
            },
            "mtproto": {
                "active": mtproto_active,
                "trial_available": mtproto_trial_available,
            },
            "whatsapp": {
                "active": whatsapp_active,
                "trial_available": whatsapp_trial_available,
            },
        },
    }


def serialize_legal_consents(user: User) -> dict:
    return {
        "version": LEGAL_CONSENTS_VERSION,
        "privacy_policy_accepted": user.privacy_policy_accepted_at is not None,
        "terms_of_use_accepted": user.terms_of_use_accepted_at is not None,
        "personal_data_consent_accepted": user.personal_data_consent_accepted_at is not None,
        "marketing_consent_granted": user.marketing_consent_granted,
        "required_consents_accepted": has_required_legal_consents(user),
        "accepted_at": {
            "privacy_policy": user.privacy_policy_accepted_at.isoformat()
            if user.privacy_policy_accepted_at
            else None,
            "terms_of_use": user.terms_of_use_accepted_at.isoformat()
            if user.terms_of_use_accepted_at
            else None,
            "personal_data": user.personal_data_consent_accepted_at.isoformat()
            if user.personal_data_consent_accepted_at
            else None,
            "marketing": user.marketing_consent_updated_at.isoformat()
            if user.marketing_consent_updated_at
            else None,
        },
    }


def serialize_vpn_product(product: Product, durations: list[int]) -> dict:
    return {
        "devices": product.devices,
        "prices": {
            currency: {str(dur): price for dur, price in dur_prices.items()}
            for currency, dur_prices in (product.prices or {}).items()
        },
        "durations": durations,
    }


def serialize_vpn_products(products: list[Product], durations: list[int]) -> list[dict]:
    return [serialize_vpn_product(p, durations) for p in products]


def serialize_mtproto_plans(config) -> list[dict]:
    """Serialize MTProto pricing from config."""
    durations = [30, 90, 180, 365]
    prices = {
        30: config.shop.MTPROTO_PRICE_30,
        90: config.shop.MTPROTO_PRICE_90,
        180: config.shop.MTPROTO_PRICE_180,
        365: config.shop.MTPROTO_PRICE_365,
    }
    return [
        {
            "duration": d,
            "price_rub": prices[d],
            "price_stars": max(1, round(prices[d] / 1.8)),
        }
        for d in durations
    ]


def serialize_whatsapp_plans(config) -> list[dict]:
    """Serialize WhatsApp pricing from config."""
    durations = [30, 90, 180, 365]
    prices = {
        30: config.shop.WHATSAPP_PRICE_30,
        90: config.shop.WHATSAPP_PRICE_90,
        180: config.shop.WHATSAPP_PRICE_180,
        365: config.shop.WHATSAPP_PRICE_365,
    }
    return [
        {
            "duration": d,
            "price_rub": prices[d],
            "price_stars": max(1, round(prices[d] / 1.8)),
        }
        for d in durations
    ]


def serialize_vpn_subscription(
    client_data: ClientData | None,
    key: str | None,
    location: str | None = None,
    cancelled_at: datetime | None = None,
    current_profile: VpnProfile | None = None,
    available_profiles: list[VpnProfile] | None = None,
    subscription_id: int | None = None,
    extra_keys: list[dict] | None = None,
) -> dict:
    payload = {
        "subscription_id": subscription_id,
        "current_profile": serialize_vpn_profile(current_profile) if current_profile else None,
        "available_profiles": serialize_vpn_profiles(available_profiles or []),
        "location": location,
        "cancelled_at": cancelled_at.isoformat() if cancelled_at else None,
        "extra_keys": extra_keys or [],
    }
    if not client_data:
        return {"active": False, **payload}

    return {
        "active": not client_data.has_subscription_expired,
        "expired": client_data.has_subscription_expired,
        "max_devices": client_data._max_devices,
        "traffic_total": client_data._traffic_total,
        "traffic_used": client_data._traffic_used,
        "traffic_up": client_data._traffic_up,
        "traffic_down": client_data._traffic_down,
        "traffic_remaining": client_data._traffic_remaining,
        "expiry_time": client_data._expiry_time,
        "key": key,
        **payload,
    }


def serialize_mtproto_subscription(
    sub: MTProtoSubscription | None,
    link: str | None,
    location: str | None = None,
    subscription_id: int | None = None,
) -> dict:
    if not sub or not sub.is_active:
        return {"active": False, "subscription_id": subscription_id}

    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "subscription_id": subscription_id,
        "active": not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "link": link,
        "location": location,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }


def serialize_whatsapp_subscription(
    sub: WhatsAppSubscription | None,
    host: str,
    public_port: int,
    location: str | None = None,
    subscription_id: int | None = None,
) -> dict:
    if not sub or not sub.is_active:
        return {"active": False, "subscription_id": subscription_id}

    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "subscription_id": subscription_id,
        "active": not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "host": host,
        "port": public_port,
        "location": location,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }


def serialize_vpn_subscription_item(
    subscription_id: int,
    client_data: ClientData | None,
    key: str | None,
    location: str | None = None,
    cancelled_at: datetime | None = None,
    current_profile: VpnProfile | None = None,
    available_profiles: list[VpnProfile] | None = None,
    extra_keys: list[dict] | None = None,
) -> dict:
    payload = serialize_vpn_subscription(
        client_data=client_data,
        key=key,
        location=location,
        cancelled_at=cancelled_at,
        current_profile=current_profile,
        available_profiles=available_profiles,
        subscription_id=subscription_id,
        extra_keys=extra_keys,
    )
    payload["expired"] = client_data.has_subscription_expired if client_data else False
    return payload


def serialize_mtproto_subscription_item(
    sub: MTProtoSubscription,
    link: str | None,
    location: str | None = None,
) -> dict:
    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "subscription_id": sub.id,
        "active": sub.is_active and not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "link": link,
        "location": location,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }


def serialize_whatsapp_subscription_item(
    sub: WhatsAppSubscription,
    host: str,
    public_port: int,
    location: str | None = None,
) -> dict:
    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "subscription_id": sub.id,
        "active": sub.is_active and not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "host": host,
        "port": public_port,
        "location": location,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }


def serialize_bundle_plans(catalog) -> list[dict]:
    """Serialize bundle products with all duration prices."""
    from app.bot.services.product_catalog import ProductCatalog

    result = []
    for bundle in catalog.get_bundles():
        durations = []
        for d in catalog.get_durations():
            durations.append({
                "duration": d,
                "price_rub": catalog.calculate_price_rub(bundle.slug, d),
                "price_stars": catalog.calculate_price_stars(bundle.slug, d),
                "discount_percent": catalog.get_discount_percent(d),
            })

        result.append({
            "slug": bundle.slug,
            "name": bundle.name,
            "emoji": bundle.emoji,
            "description": bundle.description,
            "trial_days": bundle.trial_days,
            "includes": bundle.includes,
            "durations": durations,
        })

    return result


def serialize_operator(operator: Operator) -> dict:
    return {
        "slug": operator.slug,
        "name": operator.name,
        "name_en": operator.name_en or operator.name,
        "emoji": operator.emoji,
        "order": operator.order,
    }


def serialize_operators(operators: list[Operator]) -> list[dict]:
    return [serialize_operator(op) for op in operators]


def serialize_vpn_profile(profile: VpnProfile) -> dict:
    return {
        "slug": profile.slug,
        "name": profile.name,
        "name_en": profile.name_en or profile.name,
        "emoji": profile.emoji,
        "kind": profile.kind,
        "group": profile.group,
        "order": profile.order,
    }


def serialize_vpn_profiles(profiles: list[VpnProfile]) -> list[dict]:
    return [serialize_vpn_profile(profile) for profile in profiles]


# ---------- Admin serializers ----------


def serialize_admin_user(user: User) -> dict:
    """Serialize a user for the admin users list."""
    return {
        "tg_id": user.tg_id,
        "first_name": user.first_name,
        "username": user.username,
        "operator": user.operator,
        "vpn_profile_slug": user.vpn_profile_slug,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "server_name": user.server.name if user.server else None,
        "is_trial_used": user.is_trial_used,
    }


def serialize_admin_transaction(tx: Transaction) -> dict:
    """Serialize a transaction for admin user detail."""
    return {
        "id": tx.id,
        "payment_id": tx.payment_id,
        "subscription": tx.subscription,
        "status": tx.status.value if tx.status else None,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "updated_at": tx.updated_at.isoformat() if tx.updated_at else None,
    }


def serialize_admin_user_detail(
    user: User,
    client_data: ClientData | None,
    transactions: list[Transaction],
) -> dict:
    """Serialize full user detail for admin view."""
    vpn_info = None
    if client_data:
        vpn_info = {
            "active": not client_data.has_subscription_expired,
            "expired": client_data.has_subscription_expired,
            "max_devices": client_data._max_devices,
            "traffic_total": client_data._traffic_total,
            "traffic_used": client_data._traffic_used,
            "expiry_time": client_data._expiry_time,
        }

    return {
        "tg_id": user.tg_id,
        "first_name": user.first_name,
        "username": user.username,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "server_name": user.server.name if user.server else None,
        "is_trial_used": user.is_trial_used,
        "vpn": vpn_info,
        "transactions": [serialize_admin_transaction(tx) for tx in transactions],
    }


def serialize_admin_server(server: Server) -> dict:
    """Serialize a server for the admin servers list."""
    return {
        "id": server.id,
        "name": server.name,
        "host": server.host,
        "location": server.location,
        "online": server.online,
        "max_clients": server.max_clients,
        "current_clients": server.current_clients,
        "subscription_host": server.subscription_host,
        "subscription_port": server.subscription_port,
        "subscription_path": server.subscription_path,
        "inbound_remark": server.inbound_remark,
        "client_flow": server.client_flow,
    }
