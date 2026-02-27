"""Serializers: model → JSON-safe dict for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.models import ClientData, Plan
    from app.db.models import MTProtoSubscription, User, WhatsAppSubscription


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
        "created_at": user.created_at.isoformat() if user.created_at else None,
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


def serialize_plan(plan: Plan, durations: list[int]) -> dict:
    return {
        "devices": plan.devices,
        "prices": plan.prices,
        "durations": durations,
    }


def serialize_plans(plans: list[Plan], durations: list[int]) -> list[dict]:
    return [serialize_plan(p, durations) for p in plans]


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
) -> dict:
    if not client_data:
        return {"active": False}

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
    }


def serialize_mtproto_subscription(
    sub: MTProtoSubscription | None,
    link: str | None,
) -> dict:
    if not sub or not sub.is_active:
        return {"active": False}

    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "active": not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "link": link,
    }


def serialize_whatsapp_subscription(
    sub: WhatsAppSubscription | None,
    host: str,
) -> dict:
    if not sub or not sub.is_active:
        return {"active": False}

    expired = sub.expires_at < datetime.utcnow() if sub.expires_at else True
    return {
        "active": not expired,
        "expired": expired,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "host": host,
        "port": sub.port,
    }
