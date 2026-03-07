#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import ssl
from dataclasses import asdict, dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any, Sequence
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from sqlalchemy import desc, select

from app.bot.services.mtproto import MTProtoService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.services.server_pool import ServerPoolService
from app.bot.services.vpn import VPNService
from app.bot.services.whatsapp import WhatsAppService
from app.config import load_config
from app.db.database import Database
from app.db.models import MTProtoSubscription, VPNSubscription, WhatsAppSubscription


logger = logging.getLogger("proxycraft_smoke")

DEFAULT_TCP_TIMEOUT = 5.0
DEFAULT_HTTP_TIMEOUT = 10.0
DEFAULT_RETRY_COUNT = 2


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


async def resolve_mtproto_fixture(db: Database, subscription_id: int | None) -> MTProtoSubscription | None:
    async with db.session() as session:
        if subscription_id is not None:
            return await MTProtoSubscription.get_by_id(session=session, subscription_id=subscription_id)

        query = await session.execute(
            select(MTProtoSubscription).order_by(
                desc(MTProtoSubscription.activated_at),
                desc(MTProtoSubscription.id),
            )
        )
        subscriptions = list(query.scalars().all())

    now = datetime.utcnow()
    active = [
        subscription for subscription in subscriptions
        if subscription.is_active and subscription.expires_at > now
    ]
    return active[0] if active else None


async def resolve_whatsapp_fixture(db: Database, subscription_id: int | None) -> WhatsAppSubscription | None:
    async with db.session() as session:
        if subscription_id is not None:
            return await WhatsAppSubscription.get_by_id(session=session, subscription_id=subscription_id)

        query = await session.execute(
            select(WhatsAppSubscription).order_by(
                desc(WhatsAppSubscription.activated_at),
                desc(WhatsAppSubscription.id),
            )
        )
        subscriptions = list(query.scalars().all())

    now = datetime.utcnow()
    active = [
        subscription for subscription in subscriptions
        if subscription.is_active and subscription.expires_at > now
    ]
    return active[0] if active else None


async def resolve_vpn_fixture(
    db: Database,
    vpn_service: VPNService,
    subscription_id: int | None,
) -> tuple[VPNSubscription, Any] | None:
    async with db.session() as session:
        if subscription_id is not None:
            subscription = await VPNSubscription.get_by_id(session=session, subscription_id=subscription_id)
            subscriptions: Sequence[VPNSubscription] = [subscription] if subscription else []
        else:
            query = await session.execute(
                select(VPNSubscription).order_by(
                    desc(VPNSubscription.created_at),
                    desc(VPNSubscription.id),
                )
            )
            subscriptions = list(query.scalars().all())

    for subscription in subscriptions:
        if not subscription:
            continue

        async with db.session() as session:
            loaded_subscription = await VPNSubscription.get_by_id(
                session=session,
                subscription_id=subscription.id,
            )

        if not loaded_subscription:
            continue

        try:
            client_data = await vpn_service.get_client_data_for_subscription(loaded_subscription)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to inspect VPN subscription %s during fixture discovery: %s",
                loaded_subscription.id,
                exc,
            )
            continue

        if client_data is None:
            continue

        if client_data.has_subscription_expired:
            continue

        return loaded_subscription, client_data

    return None


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
    fixture_id = env_int("SMOKE_MTPROTO_SUBSCRIPTION_ID")
    subscription = await resolve_mtproto_fixture(db=db, subscription_id=fixture_id)
    if not subscription:
        raise SmokeCheckFailure(
            "mtproto",
            "No active MTProto subscription fixture found.",
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
    probe_host = env_str("SMOKE_MTPROTO_PROBE_HOST") or host
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
    fixture_id = env_int("SMOKE_WHATSAPP_SUBSCRIPTION_ID")
    subscription = await resolve_whatsapp_fixture(db=db, subscription_id=fixture_id)
    if not subscription:
        raise SmokeCheckFailure(
            "whatsapp",
            "No active WhatsApp subscription fixture found.",
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
    probe_host = env_str("SMOKE_WHATSAPP_PROBE_HOST") or host
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
) -> SmokeCheckResult:
    fixture_id = env_int("SMOKE_VPN_SUBSCRIPTION_ID")
    await server_pool.sync_servers()

    resolved = await resolve_vpn_fixture(db=db, vpn_service=vpn_service, subscription_id=fixture_id)
    if not resolved:
        raise SmokeCheckFailure(
            "vpn",
            "No viable VPN subscription fixture found (missing active client or subscription already expired).",
        )

    subscription, client_data = resolved
    key = await vpn_service.get_key_for_subscription(subscription)
    if not key:
        raise SmokeCheckFailure(
            "vpn",
            f"Failed to generate VPN subscription URL for subscription {subscription.id}.",
            details={"subscription_id": subscription.id},
        )

    probe_url = env_str("SMOKE_VPN_PROBE_URL") or key
    probe = await with_retries(
        lambda: probe_http(probe_url, timeout=http_timeout),
        attempts=attempts,
        product="vpn",
        endpoint=probe_url,
    )

    if probe["status"] != 200 or probe["body_length"] <= 0:
        raise SmokeCheckFailure(
            "vpn",
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
            "vpn",
            "VPN client exists but its expiry has already passed.",
            endpoint=key,
            details={
                "subscription_id": subscription.id,
                "expiry_time": client_data._expiry_time,
            },
        )

    return SmokeCheckResult(
        product="vpn",
        status="passed",
        summary=f"VPN subscription URL responded with data and client exists on 3X-UI for server {subscription.server_id}.",
        endpoint=key,
        details={
            "subscription_id": subscription.id,
            "server_id": subscription.server_id,
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


async def run() -> tuple[list[SmokeCheckResult], bool]:
    config = load_config()
    db = Database(config.database)
    await db.initialize()

    tcp_timeout = float(os.getenv("SMOKE_TCP_TIMEOUT", DEFAULT_TCP_TIMEOUT))
    http_timeout = float(os.getenv("SMOKE_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT))
    attempts = int(os.getenv("SMOKE_RETRY_COUNT", DEFAULT_RETRY_COUNT))

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

        try:
            results.append(
                await check_vpn(
                    vpn_service=vpn_service,
                    server_pool=server_pool,
                    db=db,
                    http_timeout=http_timeout,
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
    results, has_failures = await run()
    print_human_summary(results)

    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))

    return 1 if has_failures else 0


if __name__ == "__main__":
    main()
