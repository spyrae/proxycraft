#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import ssl
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from app.bot.services.mtproto import MTProtoService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.services.server_pool import ServerPoolService
from app.bot.services.vpn import VPNService
from app.bot.services.whatsapp import WhatsAppService
from app.config import load_config
from app.db.database import Database
from app.db.models import MTProtoSubscription, SmokeFixture, VPNSubscription, WhatsAppSubscription
from scripts.smoke_fixture_catalog import SmokeFixtureSpec, get_fixture_specs


logger = logging.getLogger("proxycraft_smoke")

DEFAULT_TCP_TIMEOUT = 5.0
DEFAULT_HTTP_TIMEOUT = 10.0
DEFAULT_RETRY_COUNT = 2
FIXTURE_SUBSCRIPTION_OVERRIDE_ENVS = {
    "mtproto": ("SMOKE_MTPROTO_SUBSCRIPTION_ID",),
    "whatsapp": ("SMOKE_WHATSAPP_SUBSCRIPTION_ID",),
    "vpn_amsterdam": ("SMOKE_VPN_AMSTERDAM_SUBSCRIPTION_ID", "SMOKE_VPN_SUBSCRIPTION_ID"),
    "vpn_saint_petersburg": ("SMOKE_VPN_SAINT_PETERSBURG_SUBSCRIPTION_ID",),
}
VPN_PROBE_OVERRIDE_ENVS = {
    "vpn_amsterdam": ("SMOKE_VPN_AMSTERDAM_PROBE_URL", "SMOKE_VPN_PROBE_URL"),
    "vpn_saint_petersburg": ("SMOKE_VPN_SAINT_PETERSBURG_PROBE_URL", "SMOKE_VPN_PROBE_URL"),
}


@dataclass
class SmokeCheckResult:
    product: str
    status: str
    summary: str
    endpoint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class SmokeCheckFailure(RuntimeError):
    def __init__(self, product: str, summary: str, *, endpoint: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(summary)
        self.product = product
        self.summary = summary
        self.endpoint = endpoint
        self.details = details or {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production smoke checks for ProxyCraft products through real service code paths.",
    )
    parser.add_argument(
        "--product",
        choices=["all", "mtproto", "whatsapp", "vpn"],
        default="all",
        help="Run a single product check or all checks sequentially.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary in addition to human-readable lines.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def env_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return int(value)


def env_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def env_float_or_default(name: str, default: float) -> float:
    value = env_str(name)
    return float(value) if value is not None else default


def env_int_or_default(name: str, default: int) -> int:
    value = env_int(name)
    return value if value is not None else default


def resolve_public_probe_host(override: str | None, public_host: str) -> str:
    if override is None:
        return public_host

    normalized = override.strip().lower()
    if normalized.startswith("proxycraft-") or normalized in {"localhost", "127.0.0.1"}:
        logger.warning(
            "Ignoring internal smoke probe host override %s for public endpoint %s.",
            override,
            public_host,
        )
        return public_host

    return override


async def probe_tcp(host: str, port: int, *, timeout: float) -> dict[str, Any]:
    started = perf_counter()
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {"latency_ms": latency_ms}
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def probe_http(url: str, *, timeout: float) -> dict[str, Any]:
    return await asyncio.to_thread(_probe_http_sync, url, timeout)


def _probe_http_sync(url: str, timeout: float) -> dict[str, Any]:
    started = perf_counter()
    context = ssl._create_unverified_context()
    request = Request(url, headers={"User-Agent": "ProxyCraftSmoke/1.0"})
    with urlopen(request, timeout=timeout, context=context) as response:
        body = response.read(1024)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "status": response.status,
            "latency_ms": latency_ms,
            "body_preview": body.decode("utf-8", errors="replace")[:200],
            "body_length": len(body),
            "content_type": response.headers.get("Content-Type"),
        }


async def with_retries(coro_factory, *, attempts: int, product: str, endpoint: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = await coro_factory()
            if attempt > 1:
                result["attempt"] = attempt
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "%s smoke probe failed on attempt %s for %s: %s",
                product,
                attempt,
                endpoint,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(1)

    raise last_error if last_error is not None else RuntimeError(f"{product} probe failed for {endpoint}")


def fixture_override_subscription_id(fixture_key: str) -> int | None:
    for env_name in FIXTURE_SUBSCRIPTION_OVERRIDE_ENVS.get(fixture_key, ()):
        value = env_int(env_name)
        if value is not None:
            return value
    return None


def fixture_override_probe_url(fixture_key: str) -> str | None:
    for env_name in VPN_PROBE_OVERRIDE_ENVS.get(fixture_key, ()):
        value = env_str(env_name)
        if value is not None:
            return value
    return None


async def resolve_registry_fixture(db: Database, fixture_key: str) -> SmokeFixture | None:
    async with db.session() as session:
        return await SmokeFixture.get_by_key(session=session, key=fixture_key)


async def resolve_mtproto_fixture(db: Database, fixture_key: str = "mtproto") -> MTProtoSubscription | None:
    subscription_id = fixture_override_subscription_id(fixture_key)
    registry = await resolve_registry_fixture(db, fixture_key)

    async with db.session() as session:
        if subscription_id is not None:
            return await MTProtoSubscription.get_by_id(session=session, subscription_id=subscription_id)
        if registry and registry.mtproto_subscription_id:
            return await MTProtoSubscription.get_by_id(
                session=session,
                subscription_id=registry.mtproto_subscription_id,
            )

    return None


async def resolve_whatsapp_fixture(db: Database, fixture_key: str = "whatsapp") -> WhatsAppSubscription | None:
    subscription_id = fixture_override_subscription_id(fixture_key)
    registry = await resolve_registry_fixture(db, fixture_key)

    async with db.session() as session:
        if subscription_id is not None:
            return await WhatsAppSubscription.get_by_id(session=session, subscription_id=subscription_id)
        if registry and registry.whatsapp_subscription_id:
            return await WhatsAppSubscription.get_by_id(
                session=session,
                subscription_id=registry.whatsapp_subscription_id,
            )

    return None


async def resolve_vpn_fixture(
    db: Database,
    vpn_service: VPNService,
    spec: SmokeFixtureSpec,
) -> tuple[VPNSubscription, Any] | None:
    subscription_id = fixture_override_subscription_id(spec.key)
    registry = await resolve_registry_fixture(db, spec.key)

    async with db.session() as session:
        if subscription_id is not None:
            subscription = await VPNSubscription.get_by_id(
                session=session,
                subscription_id=subscription_id,
            )
        elif registry and registry.vpn_subscription_id:
            subscription = await VPNSubscription.get_by_id(
                session=session,
                subscription_id=registry.vpn_subscription_id,
            )
        else:
            subscription = None

    if not subscription:
        return None

    if not subscription.server or subscription.server.location != spec.location:
        logger.warning(
            "Smoke VPN fixture %s points to wrong location: expected %s, got %s.",
            spec.key,
            spec.location,
            subscription.server.location if subscription.server else None,
        )
        return None

    if subscription.cancelled_at is not None:
        logger.warning("Smoke VPN fixture %s is cancelled.", spec.key)
        return None

    if subscription.vpn_profile_slug != spec.vpn_profile_slug:
        logger.warning(
            "Smoke VPN fixture %s points to wrong profile: expected %s, got %s.",
            spec.key,
            spec.vpn_profile_slug,
            subscription.vpn_profile_slug,
        )
        return None

    try:
        client_data = await vpn_service.get_client_data_for_subscription(subscription)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to inspect VPN smoke fixture %s (subscription %s): %s",
            spec.key,
            subscription.id,
            exc,
        )
        return None

    if client_data is None or client_data.has_subscription_expired:
        return None

    return subscription, client_data


def parse_mtproto_endpoint(link: str) -> tuple[str, int, str]:
    parsed = urlparse(link)
    params = parse_qs(parsed.query)
    host = params.get("server", [None])[0]
    port = params.get("port", [None])[0]
    secret = params.get("secret", [None])[0]

    if not host or not port or not secret:
        raise ValueError("MTProto link is missing server/port/secret")

    return host, int(port), secret


async def check_mtproto(
    mtproto_service: MTProtoService,
    db: Database,
    tcp_timeout: float,
    attempts: int,
) -> SmokeCheckResult:
    subscription = await resolve_mtproto_fixture(db=db)
    if not subscription:
        raise SmokeCheckFailure(
            "mtproto",
            "MTProto smoke fixture is not provisioned or no longer valid.",
        )

    link = await mtproto_service.get_link_for_subscription(subscription)
    if not link:
        raise SmokeCheckFailure(
            "mtproto",
            f"Failed to generate MTProto link for subscription {subscription.id}.",
            details={"subscription_id": subscription.id},
        )

    host, port, secret = parse_mtproto_endpoint(link)
    endpoint = f"{host}:{port}"
    probe_host = resolve_public_probe_host(env_str("SMOKE_MTPROTO_PROBE_HOST"), host)
    probe = await with_retries(
        lambda: probe_tcp(probe_host, port, timeout=tcp_timeout),
        attempts=attempts,
        product="mtproto",
        endpoint=endpoint,
    )

    if not secret.startswith("ee"):
        raise SmokeCheckFailure(
            "mtproto",
            "Generated MTProto secret is not in FakeTLS format.",
            endpoint=endpoint,
            details={"subscription_id": subscription.id, "link": link},
        )

    return SmokeCheckResult(
        product="mtproto",
        status="passed",
        summary=f"MTProto link generated and endpoint {endpoint} accepted TCP connection.",
        endpoint=endpoint,
        details={
            "subscription_id": subscription.id,
            "expires_at": subscription.expires_at.isoformat(),
            "latency_ms": probe["latency_ms"],
            "link": link,
            "probe_host": probe_host,
        },
    )


async def check_whatsapp(
    whatsapp_service: WhatsAppService,
    db: Database,
    tcp_timeout: float,
    attempts: int,
) -> SmokeCheckResult:
    subscription = await resolve_whatsapp_fixture(db=db)
    if not subscription:
        raise SmokeCheckFailure(
            "whatsapp",
            "WhatsApp smoke fixture is not provisioned or no longer valid.",
        )

    connection_info = await whatsapp_service.get_connection_info_for_subscription(subscription)
    if not connection_info:
        raise SmokeCheckFailure(
            "whatsapp",
            f"Failed to resolve connection info for WhatsApp subscription {subscription.id}.",
            details={"subscription_id": subscription.id},
        )

    host, port = connection_info
    endpoint = f"{host}:{port}"
    probe_host = resolve_public_probe_host(env_str("SMOKE_WHATSAPP_PROBE_HOST"), host)
    probe = await with_retries(
        lambda: probe_tcp(probe_host, port, timeout=tcp_timeout),
        attempts=attempts,
        product="whatsapp",
        endpoint=endpoint,
    )

    return SmokeCheckResult(
        product="whatsapp",
        status="passed",
        summary=f"WhatsApp proxy endpoint {endpoint} accepted TCP connection.",
        endpoint=endpoint,
        details={
            "subscription_id": subscription.id,
            "expires_at": subscription.expires_at.isoformat(),
            "latency_ms": probe["latency_ms"],
            "probe_host": probe_host,
        },
    )


async def check_vpn(
    vpn_service: VPNService,
    server_pool: ServerPoolService,
    db: Database,
    http_timeout: float,
    attempts: int,
    spec: SmokeFixtureSpec,
) -> SmokeCheckResult:
    await server_pool.sync_servers()

    resolved = await resolve_vpn_fixture(db=db, vpn_service=vpn_service, spec=spec)
    if not resolved:
        raise SmokeCheckFailure(
            spec.key,
            f"VPN smoke fixture {spec.key} is not provisioned, expired, or points to the wrong location/profile.",
        )

    subscription, client_data = resolved
    key = await vpn_service.get_key_for_subscription(subscription)
    if not key:
        raise SmokeCheckFailure(
            spec.key,
            f"Failed to generate VPN subscription URL for subscription {subscription.id}.",
            details={"subscription_id": subscription.id},
        )

    probe_url = fixture_override_probe_url(spec.key) or key
    probe = await with_retries(
        lambda: probe_http(probe_url, timeout=http_timeout),
        attempts=attempts,
        product=spec.key,
        endpoint=probe_url,
    )

    if probe["status"] != 200 or probe["body_length"] <= 0:
        raise SmokeCheckFailure(
            spec.key,
            f"VPN subscription endpoint returned unexpected response ({probe['status']}).",
            endpoint=probe_url,
            details={
                "subscription_id": subscription.id,
                "http_status": probe["status"],
                "body_preview": probe["body_preview"],
            },
        )

    if client_data.has_subscription_expired:
        raise SmokeCheckFailure(
            spec.key,
            "VPN client exists but its expiry has already passed.",
            endpoint=key,
            details={
                "subscription_id": subscription.id,
                "expiry_time": client_data._expiry_time,
            },
        )

    return SmokeCheckResult(
        product=spec.key,
        status="passed",
        summary=(
            f"VPN smoke fixture for {spec.location} responded with data and "
            f"client exists on 3X-UI for server {subscription.server_id}."
        ),
        endpoint=key,
        details={
            "subscription_id": subscription.id,
            "server_id": subscription.server_id,
            "location": spec.location,
            "vpn_profile_slug": subscription.vpn_profile_slug,
            "expires_at_ms": client_data._expiry_time,
            "latency_ms": probe["latency_ms"],
            "http_status": probe["status"],
            "probe_url": probe_url,
        },
    )


def should_check(enabled: bool, product: str) -> SmokeCheckResult | None:
    if enabled:
        return None
    return SmokeCheckResult(
        product=product,
        status="skipped",
        summary=f"{product.upper()} is disabled in current runtime config.",
    )


async def run(product: str = "all") -> tuple[list[SmokeCheckResult], bool]:
    config = load_config()
    db = Database(config.database)
    await db.initialize()

    tcp_timeout = env_float_or_default("SMOKE_TCP_TIMEOUT", DEFAULT_TCP_TIMEOUT)
    http_timeout = env_float_or_default("SMOKE_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT)
    attempts = env_int_or_default("SMOKE_RETRY_COUNT", DEFAULT_RETRY_COUNT)

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

    results: list[SmokeCheckResult] = []
    has_failures = False

    try:
        if product in {"all", "mtproto"}:
            logger.info("Starting MTProto smoke check.")
            mtproto_skip = should_check(config.shop.MTPROTO_ENABLED, "mtproto")
            if mtproto_skip:
                results.append(mtproto_skip)
            else:
                try:
                    results.append(
                        await check_mtproto(
                            mtproto_service=mtproto_service,
                            db=db,
                            tcp_timeout=tcp_timeout,
                            attempts=attempts,
                        )
                    )
                except SmokeCheckFailure as failure:
                    has_failures = True
                    results.append(
                        SmokeCheckResult(
                            product=failure.product,
                            status="failed",
                            summary=failure.summary,
                            endpoint=failure.endpoint,
                            details=failure.details,
                        )
                    )

        if product in {"all", "whatsapp"}:
            logger.info("Starting WhatsApp smoke check.")
            whatsapp_skip = should_check(config.shop.WHATSAPP_ENABLED, "whatsapp")
            if whatsapp_skip:
                results.append(whatsapp_skip)
            else:
                try:
                    results.append(
                        await check_whatsapp(
                            whatsapp_service=whatsapp_service,
                            db=db,
                            tcp_timeout=tcp_timeout,
                            attempts=attempts,
                        )
                    )
                except SmokeCheckFailure as failure:
                    has_failures = True
                    results.append(
                        SmokeCheckResult(
                            product=failure.product,
                            status="failed",
                            summary=failure.summary,
                            endpoint=failure.endpoint,
                            details=failure.details,
                        )
                    )

        if product in {"all", "vpn"}:
            logger.info("Starting VPN smoke check.")
            for spec in get_fixture_specs("vpn"):
                try:
                    results.append(
                        await check_vpn(
                            vpn_service=vpn_service,
                            server_pool=server_pool,
                            db=db,
                            http_timeout=http_timeout,
                            attempts=attempts,
                            spec=spec,
                        )
                    )
                except SmokeCheckFailure as failure:
                    has_failures = True
                    results.append(
                        SmokeCheckResult(
                            product=failure.product,
                            status="failed",
                            summary=failure.summary,
                            endpoint=failure.endpoint,
                            details=failure.details,
                        )
                    )
    finally:
        await db.close()

    return results, has_failures


def print_human_summary(results: Sequence[SmokeCheckResult]) -> None:
    for result in results:
        line = f"[{result.status.upper()}] {result.product}: {result.summary}"
        if result.endpoint:
            line += f" | endpoint={result.endpoint}"
        print(line)


def main() -> None:
    args = parse_args()
    configure_logging()
    try:
        exit_code = asyncio.run(run_and_print(args))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    raise SystemExit(exit_code)


async def run_and_print(args: argparse.Namespace) -> int:
    results, has_failures = await run(product=args.product)
    print_human_summary(results)

    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))

    return 1 if has_failures else 0


if __name__ == "__main__":
    main()
