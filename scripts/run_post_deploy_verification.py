#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

from aiohttp import ClientSession, ClientTimeout
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.services.product_catalog import ProductCatalog
from app.bot.services.server_pool import ServerPoolService
from app.bot.services.whatsapp import WhatsAppService
from app.config import load_config
from app.db.database import Database
from app.db.models import Server
from scripts.provision_smoke_fixtures import (
    FixtureProvisionResult,
    run as provision_smoke_fixtures,
)
from scripts.smoke_fixture_catalog import get_fixture_specs
from scripts.run_smoke_checks import (
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TCP_TIMEOUT,
    SmokeCheckResult,
    env_float_or_default,
    env_int_or_default,
    env_str,
    probe_tcp,
    resolve_whatsapp_fixture,
    run as run_smoke_checks,
)


logger = logging.getLogger("proxycraft_post_deploy")

Severity = Literal["deploy-blocking", "warning-only"]
Status = Literal["passed", "warning", "failed", "skipped"]
NOTIFICATION_TIMEOUT_SECONDS = 15.0
VPN_POOL_REFRESH_TIMEOUT_SECONDS = 45.0
FIXTURE_PROVISION_BASE_TIMEOUT_SECONDS = 30.0
FIXTURE_PROVISION_PER_FIXTURE_TIMEOUT_SECONDS = 45.0
SMOKE_SUITE_TIMEOUT_SECONDS = 180.0


@dataclass
class VerificationResult:
    key: str
    severity: Severity
    status: Status
    summary: str
    endpoint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production post-deploy verification for ProxyCraft.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send Telegram alert to BOT_ADMINS when failures or warnings are detected.",
    )
    parser.add_argument(
        "--notify-warnings",
        action="store_true",
        help="Also notify on warning-only verification results.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def fixture_provision_timeout_seconds() -> float:
    return (
        FIXTURE_PROVISION_BASE_TIMEOUT_SECONDS
        + FIXTURE_PROVISION_PER_FIXTURE_TIMEOUT_SECONDS * len(get_fixture_specs())
    )


def github_context() -> dict[str, str | None]:
    repository = env_str("DEPLOY_GITHUB_REPOSITORY")
    run_id = env_str("DEPLOY_GITHUB_RUN_ID")
    sha = env_str("DEPLOY_GITHUB_SHA")
    run_url = None
    if repository and run_id:
        run_url = f"https://github.com/{repository}/actions/runs/{run_id}"
    return {
        "repository": repository,
        "run_id": run_id,
        "sha": sha,
        "run_url": run_url,
    }


async def check_bot_api_health(bot_port: int, timeout_seconds: float) -> VerificationResult:
    url = f"http://127.0.0.1:{bot_port}/api/v1/health"
    timeout = ClientTimeout(total=timeout_seconds)

    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                body = await response.json(content_type=None)
    except Exception as exception:  # noqa: BLE001
        return VerificationResult(
            key="bot_api_health",
            severity="deploy-blocking",
            status="failed",
            summary=f"Bot API health endpoint is unavailable: {exception}",
            endpoint=url,
            details={"reason": str(exception)},
        )

    if response.status != 200 or body.get("status") != "ok":
        return VerificationResult(
            key="bot_api_health",
            severity="deploy-blocking",
            status="failed",
            summary=f"Bot API health endpoint returned unexpected response ({response.status}).",
            endpoint=url,
            details={"response": body, "http_status": response.status},
        )

    return VerificationResult(
        key="bot_api_health",
        severity="deploy-blocking",
        status="passed",
        summary="Bot API health endpoint responded with status=ok.",
        endpoint=url,
        details=body,
    )


async def check_vpn_server_pool(
    server_pool: ServerPoolService,
    db: Database,
    catalog: ProductCatalog,
) -> list[VerificationResult]:
    try:
        await asyncio.wait_for(
            server_pool.sync_servers(force_refresh=True),
            timeout=VPN_POOL_REFRESH_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return [
            VerificationResult(
                key="vpn_pool_refresh",
                severity="deploy-blocking",
                status="failed",
                summary=(
                    "VPN server pool refresh exceeded "
                    f"{VPN_POOL_REFRESH_TIMEOUT_SECONDS:.0f}s and was aborted."
                ),
                details={"timeout_seconds": VPN_POOL_REFRESH_TIMEOUT_SECONDS},
            )
        ]

    async with db.session() as session:
        servers = await Server.get_all(session)

    known_locations = sorted(
        {
            location
            for profile in catalog.get_vpn_profiles()
            for location in profile.locations
            if location
        }
    )
    results: list[VerificationResult] = []

    for location in known_locations:
        location_servers = [server for server in servers if server.location == location]
        online_servers = [server for server in location_servers if server.online]
        total_capacity = sum(server.max_clients for server in online_servers)
        used_capacity = sum(server.current_clients for server in online_servers)
        utilization = round((used_capacity / total_capacity) * 100, 2) if total_capacity else None

        details = {
            "location": location,
            "configured_servers": [server.name for server in location_servers],
            "online_servers": [server.name for server in online_servers],
            "total_capacity": total_capacity,
            "used_capacity": used_capacity,
            "utilization_percent": utilization,
        }

        if not location_servers:
            results.append(
                VerificationResult(
                    key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                    severity="deploy-blocking",
                    status="failed",
                    summary=f"No VPN servers are configured for location {location}.",
                    details=details,
                )
            )
            continue

        if not online_servers:
            results.append(
                VerificationResult(
                    key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                    severity="deploy-blocking",
                    status="failed",
                    summary=f"VPN server pool for {location} has no online servers.",
                    details=details,
                )
            )
            continue

        if len(online_servers) == 1:
            results.append(
                VerificationResult(
                    key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                    severity="warning-only",
                    status="warning",
                    summary=f"VPN server pool for {location} is healthy but has only one online server.",
                    details=details,
                )
            )
            continue

        if utilization is not None and utilization >= 90:
            results.append(
                VerificationResult(
                    key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                    severity="warning-only",
                    status="warning",
                    summary=f"VPN server pool for {location} is online but utilization is high ({utilization}%).",
                    details=details,
                )
            )
            continue

        if len(online_servers) < len(location_servers):
            results.append(
                VerificationResult(
                    key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                    severity="warning-only",
                    status="warning",
                    summary=(
                        f"VPN server pool for {location} is available, but some configured servers are offline."
                    ),
                    details=details,
                )
            )
            continue

        results.append(
            VerificationResult(
                key=f"vpn_pool_{location.lower().replace(' ', '_')}",
                severity="deploy-blocking",
                status="passed",
                summary=f"VPN server pool for {location} is available and redundant.",
                details=details,
            )
        )

    return results


async def check_mtproto_runtime(config, tcp_timeout: float, attempts: int) -> VerificationResult:
    if not config.shop.MTPROTO_ENABLED:
        return VerificationResult(
            key="mtproto_runtime_health",
            severity="deploy-blocking",
            status="skipped",
            summary="MTProto is disabled in current runtime config.",
        )

    host = config.shop.MTPROTO_HOST
    port = config.shop.MTPROTO_PORT
    endpoint = f"{host}:{port}"
    probe_host = env_str("SMOKE_MTPROTO_PROBE_HOST") or host

    try:
        probe = await asyncio.wait_for(
            _probe_with_retries(
                lambda: probe_tcp(probe_host, port, timeout=tcp_timeout),
                attempts=attempts,
                endpoint=endpoint,
                product="mtproto_runtime_health",
            ),
            timeout=max(tcp_timeout * attempts + attempts, tcp_timeout + 1),
        )
    except Exception as exception:  # noqa: BLE001
        return VerificationResult(
            key="mtproto_runtime_health",
            severity="deploy-blocking",
            status="failed",
            summary=f"MTProto runtime endpoint {endpoint} did not accept TCP connection.",
            endpoint=endpoint,
            details={"reason": str(exception), "probe_host": probe_host},
        )

    return VerificationResult(
        key="mtproto_runtime_health",
        severity="deploy-blocking",
        status="passed",
        summary=f"MTProto runtime endpoint {endpoint} accepted TCP connection.",
        endpoint=endpoint,
        details={"latency_ms": probe["latency_ms"], "probe_host": probe_host},
    )


async def check_whatsapp_runtime(db: Database, config, tcp_timeout: float, attempts: int) -> VerificationResult:
    if not config.shop.WHATSAPP_ENABLED:
        return VerificationResult(
            key="whatsapp_runtime_health",
            severity="deploy-blocking",
            status="skipped",
            summary="WhatsApp proxy is disabled in current runtime config.",
        )

    whatsapp_service = WhatsAppService(config=config, session_factory=db.session)
    subscription = await resolve_whatsapp_fixture(db=db)
    if not subscription:
        return VerificationResult(
            key="whatsapp_runtime_health",
            severity="deploy-blocking",
            status="failed",
            summary="WhatsApp runtime health could not resolve the smoke fixture subscription.",
        )

    connection_info = await whatsapp_service.get_connection_info_for_subscription(subscription)
    if not connection_info:
        return VerificationResult(
            key="whatsapp_runtime_health",
            severity="deploy-blocking",
            status="failed",
            summary=f"WhatsApp runtime health could not resolve connection info for subscription {subscription.id}.",
            details={"subscription_id": subscription.id},
        )

    host, port = connection_info
    endpoint = f"{host}:{port}"
    probe_host = env_str("SMOKE_WHATSAPP_PROBE_HOST") or host

    try:
        probe = await asyncio.wait_for(
            _probe_with_retries(
                lambda: probe_tcp(probe_host, port, timeout=tcp_timeout),
                attempts=attempts,
                endpoint=endpoint,
                product="whatsapp_runtime_health",
            ),
            timeout=max(tcp_timeout * attempts + attempts, tcp_timeout + 1),
        )
    except Exception as exception:  # noqa: BLE001
        return VerificationResult(
            key="whatsapp_runtime_health",
            severity="deploy-blocking",
            status="failed",
            summary=f"WhatsApp runtime endpoint {endpoint} did not accept TCP connection.",
            endpoint=endpoint,
            details={
                "reason": str(exception),
                "probe_host": probe_host,
                "subscription_id": subscription.id,
            },
        )

    return VerificationResult(
        key="whatsapp_runtime_health",
        severity="deploy-blocking",
        status="passed",
        summary=f"WhatsApp runtime endpoint {endpoint} accepted TCP connection.",
        endpoint=endpoint,
        details={
            "latency_ms": probe["latency_ms"],
            "probe_host": probe_host,
            "subscription_id": subscription.id,
        },
    )


async def _probe_with_retries(coro_factory, *, attempts: int, endpoint: str, product: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = await coro_factory()
            if attempt > 1:
                result["attempt"] = attempt
            return result
        except Exception as exception:  # noqa: BLE001
            last_error = exception
            logger.warning(
                "%s probe failed on attempt %s for %s: %s",
                product,
                attempt,
                endpoint,
                exception,
            )
            if attempt < attempts:
                await asyncio.sleep(1)

    raise last_error if last_error is not None else RuntimeError(f"{product} probe failed for {endpoint}")


def map_fixture_results(results: Sequence[FixtureProvisionResult]) -> list[VerificationResult]:
    mapped: list[VerificationResult] = []
    for result in results:
        status: Status = "passed" if result.status == "passed" else "failed"
        mapped.append(
            VerificationResult(
                key=f"fixture_{result.key}",
                severity="deploy-blocking",
                status=status,
                summary=result.summary,
                details={
                    "product": result.product,
                    "user_tg_id": result.user_tg_id,
                    "subscription_id": result.subscription_id,
                    **(result.details or {}),
                },
            )
        )
    return mapped


def map_smoke_results(results: Sequence[SmokeCheckResult]) -> list[VerificationResult]:
    mapped: list[VerificationResult] = []
    for result in results:
        status: Status
        if result.status == "failed":
            status = "failed"
        elif result.status == "warning":
            status = "warning"
        elif result.status == "skipped":
            status = "skipped"
        else:
            status = "passed"

        mapped.append(
            VerificationResult(
                key=f"smoke_{result.product}",
                severity="deploy-blocking",
                status=status,
                summary=result.summary,
                endpoint=result.endpoint,
                details=result.details,
            )
        )
    return mapped


def has_blocking_failures(results: Sequence[VerificationResult]) -> bool:
    return any(result.severity == "deploy-blocking" and result.status == "failed" for result in results)


def print_human_summary(results: Sequence[VerificationResult]) -> None:
    for result in results:
        line = f"[{result.status.upper()}] ({result.severity}) {result.key}: {result.summary}"
        if result.endpoint:
            line += f" | endpoint={result.endpoint}"
        print(line)


def build_notification_text(results: Sequence[VerificationResult], context: dict[str, str | None]) -> str:
    blocking_failures = [result for result in results if result.severity == "deploy-blocking" and result.status == "failed"]
    warnings = [result for result in results if result.status == "warning"]
    icon = "🚨" if blocking_failures else "⚠️"
    title = "ProxyCraft post-deploy verification failed" if blocking_failures else "ProxyCraft post-deploy warnings"

    lines = [f"{icon} <b>{title}</b>"]
    if context.get("sha"):
        lines.append(f"Commit: <code>{context['sha'][:7]}</code>")
    if context.get("run_url"):
        lines.append(f'<a href="{context["run_url"]}">GitHub Actions run</a>')

    if blocking_failures:
        lines.append("")
        lines.append("<b>Deploy-blocking failures</b>")
        for result in blocking_failures:
            lines.append(f"• <b>{result.key}</b>: {result.summary}")

    if warnings:
        lines.append("")
        lines.append("<b>Warnings</b>")
        for result in warnings:
            lines.append(f"• <b>{result.key}</b>: {result.summary}")

    return "\n".join(lines)


async def maybe_notify_admins(
    *,
    config,
    results: Sequence[VerificationResult],
    notify: bool,
    notify_warnings: bool,
) -> None:
    if not notify:
        return

    blocking_failures = [result for result in results if result.severity == "deploy-blocking" and result.status == "failed"]
    warnings = [result for result in results if result.status == "warning"]

    if not blocking_failures and not (notify_warnings and warnings):
        return

    bot = Bot(
        token=config.bot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    try:
        message = build_notification_text(results, github_context())
        for chat_id in config.bot.ADMINS:
            try:
                await asyncio.wait_for(
                    bot.send_message(chat_id=chat_id, text=message),
                    timeout=NOTIFICATION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "Post-deploy alert delivery to %s exceeded %.1fs and was skipped.",
                    chat_id,
                    NOTIFICATION_TIMEOUT_SECONDS,
                )
            except Exception as exception:  # noqa: BLE001
                logger.warning(
                    "Post-deploy alert delivery to %s failed: %s",
                    chat_id,
                    exception,
                )
    finally:
        await bot.session.close()


async def run_verification(*, notify: bool, notify_warnings: bool) -> tuple[list[VerificationResult], int]:
    config = load_config()
    db = Database(config.database)
    await db.initialize()

    results: list[VerificationResult] = []
    tcp_timeout = env_float_or_default("SMOKE_TCP_TIMEOUT", DEFAULT_TCP_TIMEOUT)
    http_timeout = env_float_or_default("SMOKE_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT)
    attempts = env_int_or_default("SMOKE_RETRY_COUNT", DEFAULT_RETRY_COUNT)

    server_pool = ServerPoolService(config=config, session=db.session)
    product_catalog = ProductCatalog()
    fixture_timeout = fixture_provision_timeout_seconds()

    try:
        results.append(await check_bot_api_health(config.bot.PORT, http_timeout))
        results.extend(await check_vpn_server_pool(server_pool=server_pool, db=db, catalog=product_catalog))

        try:
            fixture_results = await asyncio.wait_for(
                provision_smoke_fixtures(),
                timeout=fixture_timeout,
            )
        except TimeoutError:
            fixture_results = [
                FixtureProvisionResult(
                    key="fixtures",
                    product="all",
                    status="failed",
                    summary=(
                        "Smoke fixture provisioning exceeded "
                        f"{fixture_timeout:.0f}s and was aborted."
                    ),
                    user_tg_id=0,
                    details={"timeout_seconds": fixture_timeout},
                )
            ]
        results.extend(map_fixture_results(fixture_results))

        results.append(await check_mtproto_runtime(config=config, tcp_timeout=tcp_timeout, attempts=attempts))
        results.append(await check_whatsapp_runtime(db=db, config=config, tcp_timeout=tcp_timeout, attempts=attempts))

        try:
            smoke_results, _ = await asyncio.wait_for(
                run_smoke_checks(product="all"),
                timeout=SMOKE_SUITE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            smoke_results = [
                SmokeCheckResult(
                    product="all",
                    status="failed",
                    summary=(
                        "Smoke suite exceeded "
                        f"{SMOKE_SUITE_TIMEOUT_SECONDS:.0f}s and was aborted."
                    ),
                )
            ]
        results.extend(map_smoke_results(smoke_results))

        await maybe_notify_admins(
            config=config,
            results=results,
            notify=notify,
            notify_warnings=notify_warnings,
        )
    finally:
        await db.close()

    exit_code = 1 if has_blocking_failures(results) else 0
    return results, exit_code


def main() -> None:
    args = parse_args()
    configure_logging()

    try:
        results, exit_code = asyncio.run(
            run_verification(
                notify=args.notify,
                notify_warnings=args.notify_warnings,
            )
        )
    except KeyboardInterrupt:
        raise SystemExit(130) from None

    print_human_summary(results)
    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
