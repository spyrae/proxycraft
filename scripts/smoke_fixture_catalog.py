from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeFixtureSpec:
    key: str
    product: str
    user_env: str
    default_tg_id: int
    first_name: str
    username: str
    location: str | None = None
    vpn_profile_slug: str | None = None
    devices: int = 1
    duration_days: int = 3650


SMOKE_FIXTURE_SPECS: tuple[SmokeFixtureSpec, ...] = (
    SmokeFixtureSpec(
        key="vpn_amsterdam",
        product="vpn",
        user_env="SMOKE_FIXTURE_TG_ID_VPN_AMSTERDAM",
        default_tg_id=990001001,
        first_name="Smoke VPN Amsterdam",
        username="smoke_vpn_ams",
        location="Amsterdam",
        vpn_profile_slug="ams-universal",
    ),
    SmokeFixtureSpec(
        key="vpn_saint_petersburg",
        product="vpn",
        user_env="SMOKE_FIXTURE_TG_ID_VPN_SAINT_PETERSBURG",
        default_tg_id=990001002,
        first_name="Smoke VPN Saint Petersburg",
        username="smoke_vpn_spb",
        location="Saint Petersburg",
        vpn_profile_slug="spb-standard",
    ),
    SmokeFixtureSpec(
        key="mtproto",
        product="mtproto",
        user_env="SMOKE_FIXTURE_TG_ID_MTPROTO",
        default_tg_id=990001003,
        first_name="Smoke MTProto",
        username="smoke_mtproto",
    ),
    SmokeFixtureSpec(
        key="whatsapp",
        product="whatsapp",
        user_env="SMOKE_FIXTURE_TG_ID_WHATSAPP",
        default_tg_id=990001004,
        first_name="Smoke WhatsApp",
        username="smoke_whatsapp",
    ),
)


def get_fixture_spec(key: str) -> SmokeFixtureSpec | None:
    return next((spec for spec in SMOKE_FIXTURE_SPECS if spec.key == key), None)


def get_fixture_specs(product: str | None = None) -> list[SmokeFixtureSpec]:
    if product is None:
        return list(SMOKE_FIXTURE_SPECS)
    return [spec for spec in SMOKE_FIXTURE_SPECS if spec.product == product]
