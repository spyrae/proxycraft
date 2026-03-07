#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from app.bot.services.mtproto import MTProtoService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.services.server_pool import ServerPoolService
from app.bot.services.vpn import VPNService
from app.bot.services.whatsapp import WhatsAppService
from app.config import load_config
from app.db.database import Database
from app.db.models import MTProtoSubscription, SmokeFixture, User, VPNSubscription, WhatsAppSubscription
from scripts.smoke_fixture_catalog import SmokeFixtureSpec, get_fixture_specs


logger = logging.getLogger("proxycraft_smoke_provision")

VPN_VALIDATION_ATTEMPTS = 4
VPN_VALIDATION_BACKOFF_SECONDS = 2
VPN_REPLACEMENT_ATTEMPTS = 3
VPN_REPLACEMENT_BACKOFF_SECONDS = 3


@dataclass
class FixtureProvisionResult:
    key: str
    product: str
    status: str
    summary: str
    user_tg_id: int
    subscription_id: int | None = None
    details: dict[str, Any] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision stable production smoke fixtures for ProxyCraft products.",
    )
    parser.add_argument(
        "--product",
        choices=["all", "mtproto", "whatsapp", "vpn"],
        default="all",
        help="Limit provisioning to a single product family.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def fixture_tg_id(spec: SmokeFixtureSpec) -> int:
    raw = os.getenv(spec.user_env)
    if raw and raw.strip():
        return int(raw.strip())
    return spec.default_tg_id


def deterministic_vpn_id(spec: SmokeFixtureSpec) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"proxycraft-smoke:{spec.key}"))


async def ensure_user(db: Database, spec: SmokeFixtureSpec) -> User:
    tg_id = fixture_tg_id(spec)
    vpn_id = deterministic_vpn_id(spec)
    source_invite_name = f"smoke-fixture:{spec.key}"

    async with db.session() as session:
        user = await User.get(session=session, tg_id=tg_id)
        if not user:
            user = await User.create(
                session=session,
                tg_id=tg_id,
                vpn_id=vpn_id,
                first_name=spec.first_name,
                username=spec.username,
                language_code="en",
                source_invite_name=source_invite_name,
                auto_renew=False,
                balance=0,
                vpn_profile_slug=spec.vpn_profile_slug,
                operator=None,
                vpn_cancelled_at=None,
            )
            if not user:
                raise RuntimeError(f"Failed to create smoke user for fixture {spec.key}")
            return user

        await User.update(
            session=session,
            tg_id=tg_id,
            vpn_id=user.vpn_id or vpn_id,
            first_name=spec.first_name,
            username=spec.username,
            language_code="en",
            source_invite_name=source_invite_name,
            auto_renew=False,
            vpn_profile_slug=spec.vpn_profile_slug if spec.product == "vpn" else user.vpn_profile_slug,
            operator=None if spec.product == "vpn" else user.operator,
        )
        refreshed = await User.get(session=session, tg_id=tg_id)
        if not refreshed:
            raise RuntimeError(f"Failed to refresh smoke user for fixture {spec.key}")
        return refreshed


async def ensure_fixture_registry(db: Database, spec: SmokeFixtureSpec, user_tg_id: int) -> SmokeFixture:
    async with db.session() as session:
        fixture = await SmokeFixture.get_by_key(session=session, key=spec.key)
        if fixture:
            updated = await SmokeFixture.update(
                session=session,
                key=spec.key,
                product=spec.product,
                location=spec.location,
                user_tg_id=user_tg_id,
            )
            if not updated:
                raise RuntimeError(f"Failed to update smoke fixture registry for {spec.key}")
            return updated

        created = await SmokeFixture.create(
            session=session,
            key=spec.key,
            product=spec.product,
            location=spec.location,
            user_tg_id=user_tg_id,
        )
        if not created:
            raise RuntimeError(f"Failed to create smoke fixture registry for {spec.key}")
        return created


async def load_registry_subscription(db: Database, fixture: SmokeFixture, spec: SmokeFixtureSpec):
    async with db.session() as session:
        if spec.product == "vpn" and fixture.vpn_subscription_id:
            return await VPNSubscription.get_by_id(session=session, subscription_id=fixture.vpn_subscription_id)
        if spec.product == "mtproto" and fixture.mtproto_subscription_id:
            return await MTProtoSubscription.get_by_id(session=session, subscription_id=fixture.mtproto_subscription_id)
        if spec.product == "whatsapp" and fixture.whatsapp_subscription_id:
            return await WhatsAppSubscription.get_by_id(session=session, subscription_id=fixture.whatsapp_subscription_id)
    return None


async def update_registry_subscription(
    db: Database,
    spec: SmokeFixtureSpec,
    subscription_id: int | None,
) -> SmokeFixture:
    updates = {
        "vpn_subscription_id": None,
        "mtproto_subscription_id": None,
        "whatsapp_subscription_id": None,
    }
    if spec.product == "vpn":
        updates["vpn_subscription_id"] = subscription_id
    elif spec.product == "mtproto":
        updates["mtproto_subscription_id"] = subscription_id
    else:
        updates["whatsapp_subscription_id"] = subscription_id

    async with db.session() as session:
        updated = await SmokeFixture.update(session=session, key=spec.key, **updates)
        if not updated:
            raise RuntimeError(f"Failed to persist subscription id for smoke fixture {spec.key}")
        return updated


async def cancel_vpn_fixture_subscription(
    db: Database,
    subscription: VPNSubscription | None,
) -> None:
    if subscription and subscription.cancelled_at is None:
        async with db.session() as session:
            await VPNSubscription.cancel(
                session=session,
                subscription_id=subscription.id,
            )


async def create_vpn_fixture_subscription(
    db: Database,
    spec: SmokeFixtureSpec,
    user: User,
    vpn_service: VPNService,
) -> VPNSubscription | None:
    async with db.session() as session:
        await User.update(
            session=session,
            tg_id=user.tg_id,
            vpn_profile_slug=spec.vpn_profile_slug,
            operator=None,
            auto_renew=False,
            vpn_cancelled_at=None,
        )

    user.vpn_profile_slug = spec.vpn_profile_slug
    user.operator = None

    return await vpn_service.create_subscription_instance(
        user=user,
        devices=spec.devices,
        duration=spec.duration_days,
        location=spec.location,
    )


async def validate_vpn_fixture_subscription(
    spec: SmokeFixtureSpec,
    vpn_service: VPNService,
    subscription: VPNSubscription,
) -> tuple[VPNSubscription | None, Any | None]:
    current_subscription = subscription

    for attempt in range(1, VPN_VALIDATION_ATTEMPTS + 1):
        reloaded = await vpn_service.get_subscription(subscription.id)
        if reloaded:
            current_subscription = reloaded
        else:
            logger.warning(
                "VPN smoke fixture %s validation attempt %s/%s: subscription %s not found.",
                spec.key,
                attempt,
                VPN_VALIDATION_ATTEMPTS,
                subscription.id,
            )
            return None, None

        if current_subscription.cancelled_at is not None:
            logger.warning(
                "VPN smoke fixture %s validation attempt %s/%s: subscription %s is cancelled.",
                spec.key,
                attempt,
                VPN_VALIDATION_ATTEMPTS,
                subscription.id,
            )
            return current_subscription, None

        if not current_subscription.server or current_subscription.server.location != spec.location:
            logger.warning(
                "VPN smoke fixture %s validation attempt %s/%s: subscription %s resolved to wrong location.",
                spec.key,
                attempt,
                VPN_VALIDATION_ATTEMPTS,
                subscription.id,
            )
            return current_subscription, None

        client_data = await vpn_service.get_client_data_for_subscription(current_subscription)
        if client_data and not client_data.has_subscription_expired:
            return current_subscription, client_data

        if attempt < VPN_VALIDATION_ATTEMPTS:
            logger.warning(
                "VPN smoke fixture %s validation attempt %s/%s did not find an active client for subscription %s. Retrying in %ss.",
                spec.key,
                attempt,
                VPN_VALIDATION_ATTEMPTS,
                subscription.id,
                VPN_VALIDATION_BACKOFF_SECONDS,
            )
            await asyncio.sleep(VPN_VALIDATION_BACKOFF_SECONDS)

    logger.error(
        "VPN smoke fixture %s failed validation after %s attempts for subscription %s.",
        spec.key,
        VPN_VALIDATION_ATTEMPTS,
        subscription.id,
    )
    return current_subscription, None


async def replace_vpn_fixture_subscription(
    db: Database,
    spec: SmokeFixtureSpec,
    user: User,
    vpn_service: VPNService,
    old_subscription: VPNSubscription | None = None,
) -> tuple[VPNSubscription | None, Any | None]:
    replacement: VPNSubscription | None = None
    replacement_client_data = None

    for attempt in range(1, VPN_REPLACEMENT_ATTEMPTS + 1):
        replacement = await create_vpn_fixture_subscription(db, spec, user, vpn_service)
        if not replacement:
            logger.warning(
                "VPN smoke fixture %s replacement attempt %s/%s failed during creation.",
                spec.key,
                attempt,
                VPN_REPLACEMENT_ATTEMPTS,
            )
        else:
            replacement, replacement_client_data = await validate_vpn_fixture_subscription(
                spec=spec,
                vpn_service=vpn_service,
                subscription=replacement,
            )
            if replacement and replacement_client_data:
                if old_subscription and old_subscription.id != replacement.id:
                    await cancel_vpn_fixture_subscription(db, old_subscription)
                await update_registry_subscription(db, spec, replacement.id)
                return replacement, replacement_client_data

            if replacement:
                logger.warning(
                    "VPN smoke fixture %s replacement attempt %s/%s created subscription %s but validation failed. Cancelling replacement.",
                    spec.key,
                    attempt,
                    VPN_REPLACEMENT_ATTEMPTS,
                    replacement.id,
                )
                await cancel_vpn_fixture_subscription(db, replacement)

        if attempt < VPN_REPLACEMENT_ATTEMPTS:
            await asyncio.sleep(VPN_REPLACEMENT_BACKOFF_SECONDS)

    logger.error(
        "VPN smoke fixture %s replacement failed after %s attempts.",
        spec.key,
        VPN_REPLACEMENT_ATTEMPTS,
    )
    return None, None


async def ensure_mtproto_fixture(
    db: Database,
    spec: SmokeFixtureSpec,
    user: User,
    fixture: SmokeFixture,
    mtproto_service: MTProtoService,
) -> FixtureProvisionResult:
    target_expiry = datetime.utcnow() + timedelta(days=spec.duration_days)
    subscription = await load_registry_subscription(db, fixture, spec)

    async with db.session() as session:
        if not subscription:
            subscription = await MTProtoSubscription.get_latest_by_user(
                session=session,
                user_tg_id=user.tg_id,
                active_first=False,
            )

        if not subscription:
            secret = await mtproto_service.activate(user.tg_id, spec.duration_days, is_trial=False)
            if not secret:
                raise RuntimeError("Failed to create MTProto smoke subscription.")
            subscription = await MTProtoSubscription.get_latest_by_user(
                session=session,
                user_tg_id=user.tg_id,
                active_first=False,
            )
        else:
            subscription = await MTProtoSubscription.update_expiry(
                session=session,
                user_tg_id=user.tg_id,
                expires_at=target_expiry,
                subscription_id=subscription.id,
            )

    if not subscription:
        raise RuntimeError("MTProto smoke subscription is missing after provisioning.")

    await mtproto_service.sync_runtime_config()
    await update_registry_subscription(db, spec, subscription.id)
    return FixtureProvisionResult(
        key=spec.key,
        product=spec.product,
        status="ready",
        summary="MTProto smoke fixture is active and synchronized.",
        user_tg_id=user.tg_id,
        subscription_id=subscription.id,
        details={
            "expires_at": subscription.expires_at.isoformat(),
            "secret_prefix": subscription.secret[:8],
        },
    )


async def ensure_whatsapp_fixture(
    db: Database,
    spec: SmokeFixtureSpec,
    user: User,
    fixture: SmokeFixture,
    whatsapp_service: WhatsAppService,
) -> FixtureProvisionResult:
    target_expiry = datetime.utcnow() + timedelta(days=spec.duration_days)
    subscription = await load_registry_subscription(db, fixture, spec)

    async with db.session() as session:
        if not subscription:
            subscription = await WhatsAppSubscription.get_latest_by_user(
                session=session,
                user_tg_id=user.tg_id,
                active_first=False,
            )

        if not subscription:
            port = await whatsapp_service.activate(user.tg_id, spec.duration_days, is_trial=False)
            if not port:
                raise RuntimeError("Failed to create WhatsApp smoke subscription.")
            subscription = await WhatsAppSubscription.get_latest_by_user(
                session=session,
                user_tg_id=user.tg_id,
                active_first=False,
            )
        else:
            subscription = await WhatsAppSubscription.update_expiry(
                session=session,
                user_tg_id=user.tg_id,
                expires_at=target_expiry,
                subscription_id=subscription.id,
            )

    if not subscription:
        raise RuntimeError("WhatsApp smoke subscription is missing after provisioning.")

    await whatsapp_service.startup_sync()
    await update_registry_subscription(db, spec, subscription.id)
    return FixtureProvisionResult(
        key=spec.key,
        product=spec.product,
        status="ready",
        summary="WhatsApp smoke fixture is active and synchronized.",
        user_tg_id=user.tg_id,
        subscription_id=subscription.id,
        details={
            "expires_at": subscription.expires_at.isoformat(),
            "port": subscription.port,
        },
    )


async def find_vpn_subscription_for_location(
    db: Database,
    user_tg_id: int,
    location: str,
) -> VPNSubscription | None:
    async with db.session() as session:
        subscriptions = await VPNSubscription.list_by_user(session=session, user_tg_id=user_tg_id)

    for subscription in subscriptions:
        if subscription.cancelled_at is not None:
            continue
        if subscription.server and subscription.server.location == location:
            return subscription
    return None


async def ensure_vpn_fixture(
    db: Database,
    spec: SmokeFixtureSpec,
    user: User,
    fixture: SmokeFixture,
    vpn_service: VPNService,
) -> FixtureProvisionResult:
    if not spec.location or not spec.vpn_profile_slug:
        raise RuntimeError(f"VPN fixture spec {spec.key} is incomplete.")

    subscription = await load_registry_subscription(db, fixture, spec)
    if subscription and (
        not subscription.server
        or subscription.server.location != spec.location
    ):
        subscription = None

    if not subscription:
        subscription = await find_vpn_subscription_for_location(db, user.tg_id, spec.location)

    if not subscription:
        subscription, client_data = await replace_vpn_fixture_subscription(
            db=db,
            spec=spec,
            user=user,
            vpn_service=vpn_service,
        )
    else:
        client_data = None

        if subscription.cancelled_at is not None:
            async with db.session() as session:
                await VPNSubscription.update(
                    session=session,
                    subscription_id=subscription.id,
                    cancelled_at=None,
                )
            subscription = await vpn_service.get_subscription(subscription.id)

        if subscription.vpn_profile_slug != spec.vpn_profile_slug:
            changed = await vpn_service.change_vpn_profile(
                user=user,
                new_profile_slug=spec.vpn_profile_slug,
                subscription_id=subscription.id,
            )
            if not changed:
                logger.warning(
                    "Failed to switch VPN smoke fixture %s to profile %s, recreating subscription.",
                    spec.key,
                    spec.vpn_profile_slug,
                )
                subscription, client_data = await replace_vpn_fixture_subscription(
                    db=db,
                    spec=spec,
                    user=user,
                    vpn_service=vpn_service,
                    old_subscription=subscription,
                )
            else:
                subscription = await vpn_service.get_subscription(subscription.id)

        if subscription and not client_data:
            changed = await vpn_service.change_subscription(
                user=user,
                devices=spec.devices,
                duration=spec.duration_days,
                subscription_id=subscription.id,
            )
            if not changed:
                logger.warning(
                    "Failed to refresh VPN smoke fixture %s in place, recreating subscription.",
                    spec.key,
                )
                subscription, client_data = await replace_vpn_fixture_subscription(
                    db=db,
                    spec=spec,
                    user=user,
                    vpn_service=vpn_service,
                    old_subscription=subscription,
                )
            else:
                subscription = await vpn_service.get_subscription(subscription.id)

        if subscription and not client_data:
            subscription, client_data = await validate_vpn_fixture_subscription(
                spec=spec,
                vpn_service=vpn_service,
                subscription=subscription,
            )

            if not client_data:
                logger.warning(
                    "VPN smoke fixture %s failed post-update validation, recreating subscription.",
                    spec.key,
                )
                subscription, client_data = await replace_vpn_fixture_subscription(
                    db=db,
                    spec=spec,
                    user=user,
                    vpn_service=vpn_service,
                    old_subscription=subscription,
                )

    if not subscription or not client_data:
        raise RuntimeError(f"VPN smoke fixture {spec.key} could not be provisioned.")

    await update_registry_subscription(db, spec, subscription.id)
    return FixtureProvisionResult(
        key=spec.key,
        product=spec.product,
        status="ready",
        summary=f"VPN smoke fixture for {spec.location} is active.",
        user_tg_id=user.tg_id,
        subscription_id=subscription.id,
        details={
            "location": spec.location,
            "server_id": subscription.server_id,
            "vpn_profile_slug": subscription.vpn_profile_slug,
            "expires_at_ms": client_data._expiry_time,
        },
    )


async def provision_fixture(
    db: Database,
    spec: SmokeFixtureSpec,
    vpn_service: VPNService,
    mtproto_service: MTProtoService,
    whatsapp_service: WhatsAppService,
) -> FixtureProvisionResult:
    user = await ensure_user(db, spec)
    fixture = await ensure_fixture_registry(db, spec, user.tg_id)

    if spec.product == "vpn":
        return await ensure_vpn_fixture(db, spec, user, fixture, vpn_service)
    if spec.product == "mtproto":
        return await ensure_mtproto_fixture(db, spec, user, fixture, mtproto_service)
    if spec.product == "whatsapp":
        return await ensure_whatsapp_fixture(db, spec, user, fixture, whatsapp_service)
    raise RuntimeError(f"Unsupported smoke fixture product: {spec.product}")


async def run(*, product: str | None = None) -> list[FixtureProvisionResult]:
    config = load_config()
    db = Database(config.database)
    await db.initialize()

    server_pool = ServerPoolService(config=config, session=db.session)
    product_catalog = ProductCatalog()
    vpn_service = VPNService(
        config=config,
        session=db.session,
        server_pool_service=server_pool,
        catalog=product_catalog,
    )
    mtproto_service = MTProtoService(config=config, session_factory=db.session)
    whatsapp_service = WhatsAppService(config=config, session_factory=db.session)

    results: list[FixtureProvisionResult] = []
    try:
        await server_pool.sync_servers()
        selected_product = None if product in {None, "all"} else product
        for spec in get_fixture_specs(product=selected_product):
            logger.info("Provisioning smoke fixture %s.", spec.key)
            if spec.product == "mtproto" and not config.shop.MTPROTO_ENABLED:
                results.append(
                    FixtureProvisionResult(
                        key=spec.key,
                        product=spec.product,
                        status="skipped",
                        summary="MTProto is disabled in current runtime config.",
                        user_tg_id=fixture_tg_id(spec),
                    )
                )
                continue
            if spec.product == "whatsapp" and not config.shop.WHATSAPP_ENABLED:
                results.append(
                    FixtureProvisionResult(
                        key=spec.key,
                        product=spec.product,
                        status="skipped",
                        summary="WhatsApp is disabled in current runtime config.",
                        user_tg_id=fixture_tg_id(spec),
                    )
                )
                continue
            results.append(
                await provision_fixture(
                    db=db,
                    spec=spec,
                    vpn_service=vpn_service,
                    mtproto_service=mtproto_service,
                    whatsapp_service=whatsapp_service,
                )
            )
    finally:
        await db.close()

    return results


def print_human_summary(results: list[FixtureProvisionResult]) -> None:
    for result in results:
        line = f"[{result.status.upper()}] {result.key}: {result.summary} | tg_id={result.user_tg_id}"
        if result.subscription_id is not None:
            line += f" subscription_id={result.subscription_id}"
        print(line)


def main() -> None:
    args = parse_args()
    configure_logging()
    results = asyncio.run(run(product=args.product))
    print_human_summary(results)
    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
