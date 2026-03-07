#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from aiohttp import ClientSession, ClientTimeout
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.services.mtproto import MTProtoService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.services.server_pool import ServerPoolService
from app.bot.services.vpn import VPNService
from app.bot.services.whatsapp import WhatsAppService
from app.config import load_config
from app.db.database import Database
from app.db.models import GeoProbeResult, GeoProbeRun
from scripts.provision_smoke_fixtures import run as provision_smoke_fixtures
from scripts.run_smoke_checks import (
    DEFAULT_HTTP_TIMEOUT,
    parse_mtproto_endpoint,
    resolve_mtproto_fixture,
    resolve_vpn_fixture,
    resolve_whatsapp_fixture,
    env_float_or_default,
    env_int_or_default,
    env_str,
)
from scripts.smoke_fixture_catalog import get_fixture_specs


logger = logging.getLogger("proxycraft_geo_probes")

CHECK_HOST_BASE_URL = "https://check-host.net"
CHECK_HOST_NODE_CATALOG_TIMEOUT_SECONDS = 10.0
CHECK_HOST_RESULT_POLL_ATTEMPTS = 12
CHECK_HOST_RESULT_POLL_INTERVAL_SECONDS = 3.0
NOTIFICATION_TIMEOUT_SECONDS = 15.0
FIXTURE_PROVISION_TIMEOUT_SECONDS = 300.0

Region = Literal["sea", "eu", "ru_friendly"]
TargetType = Literal["http", "tcp"]

REGION_COUNTRY_PRIORITY: dict[Region, tuple[str, ...]] = {
    "sea": ("SG", "ID", "MY", "TH", "VN", "PH", "HK"),
    "eu": ("NL", "DE", "GB", "CH", "FR", "PL", "SE", "FI", "ES", "IT", "PT"),
    "ru_friendly": ("RU", "KZ", "AM", "RS", "TR", "GE", "UZ", "BY"),
}
REGION_NODE_ENV: dict[Region, str] = {
    "sea": "GEO_PROBE_PREFERRED_NODES_SEA",
    "eu": "GEO_PROBE_PREFERRED_NODES_EU",
    "ru_friendly": "GEO_PROBE_PREFERRED_NODES_RU_FRIENDLY",
}
REGION_LABELS: dict[Region, str] = {
    "sea": "SEA",
    "eu": "EU",
    "ru_friendly": "RU-friendly",
}


@dataclass(frozen=True)
class CheckHostNode:
    node_id: str
    country_code: str | None = None
    country_name: str | None = None
    city: str | None = None
    asn: str | None = None


@dataclass(frozen=True)
class GeoProbeTarget:
    key: str
    product: str
    region_scope: str
    target_type: TargetType
    endpoint: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeoProbeObservation:
    product: str
    target_type: TargetType
    endpoint: str
    probe_scope: str
    probe_region: str
    status: str
    summary: str
    probe_node: str | None = None
    probe_country: str | None = None
    probe_city: str | None = None
    probe_asn: str | None = None
    latency_ms: float | None = None
    http_status: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run external geo-probes for ProxyCraft public VPN/Proxy endpoints.",
    )
    parser.add_argument(
        "--product",
        choices=["all", "mtproto", "whatsapp", "vpn"],
        default="all",
        help="Limit probing to a single product family or run all checks.",
    )
    parser.add_argument(
        "--trigger",
        choices=["manual", "scheduled"],
        default="manual",
        help="Execution source persisted in the geo-probe run record.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    parser.add_argument("--notify", action="store_true", help="Notify BOT_ADMINS on failures or warnings.")
    parser.add_argument(
        "--notify-warnings",
        action="store_true",
        help="Also notify on warning-only probe outcomes.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def normalize_timeout(name: str, default: float) -> float:
    value = env_float_or_default(name, default)
    return value if value > 0 else default


def normalize_attempts(name: str, default: int) -> int:
    value = env_int_or_default(name, default)
    return value if value > 0 else default


def preferred_nodes(region: Region) -> list[str]:
    value = env_str(REGION_NODE_ENV[region])
    if not value:
        return []
    return [node.strip() for node in value.split(",") if node.strip()]


def github_context() -> dict[str, str | None]:
    repository = env_str("GITHUB_REPOSITORY")
    run_id = env_str("GITHUB_RUN_ID")
    sha = env_str("GITHUB_SHA")
    server_url = env_str("GITHUB_SERVER_URL") or "https://github.com"
    run_url = None
    if repository and run_id:
        run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
    return {
        "repository": repository,
        "run_id": run_id,
        "sha": sha,
        "run_url": run_url,
    }


def _coerce_status_code(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_latency_ms(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return round(float(value) * 1000, 2)
    except (TypeError, ValueError):
        return None


def _parse_node_metadata(node_id: str, raw: Any) -> CheckHostNode:
    if isinstance(raw, dict):
        country_code = raw.get("country_code") or raw.get("countryCode")
        country_name = raw.get("country") or raw.get("country_name")
        city = raw.get("city")
        location = raw.get("location")
        if isinstance(location, list):
            if not country_code and len(location) > 0 and location[0]:
                country_code = str(location[0])
            if not country_name and len(location) > 1 and location[1]:
                country_name = str(location[1])
            if not city and len(location) > 2 and location[2]:
                city = str(location[2])
        asn = raw.get("asn") or raw.get("provider")
        return CheckHostNode(
            node_id=node_id,
            country_code=str(country_code).upper() if country_code else None,
            country_name=str(country_name) if country_name else None,
            city=str(city) if city else None,
            asn=str(asn) if asn else None,
        )

    parts = [str(item).strip() for item in raw if item is not None and item != ""] if isinstance(raw, list) else []
    country_code = next((item.upper() for item in parts if len(item) == 2 and item.isalpha()), None)

    country_name: str | None = None
    city: str | None = None
    asn: str | None = None
    if parts:
        if country_code and parts[0].upper() == country_code:
            country_name = parts[1] if len(parts) > 1 else None
            city = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else None)
        else:
            country_name = parts[0]
            city = parts[1] if len(parts) > 1 else None
        if len(parts) >= 4:
            asn = parts[-1]

    return CheckHostNode(
        node_id=node_id,
        country_code=country_code,
        country_name=country_name,
        city=city,
        asn=asn,
    )


def _unwrap_node_payload(payload: Any) -> Any | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        for item in payload:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], (list, dict)):
                nested = _unwrap_node_payload(item)
                if nested is not None:
                    return nested
            if isinstance(item, (list, dict)):
                return item
        return payload if payload else None
    return payload


def _parse_tcp_payload(node_payload: Any) -> tuple[str, float | None, dict[str, Any]]:
    sample = _unwrap_node_payload(node_payload)
    if sample is None:
        raise RuntimeError("Check-Host TCP result is not ready yet.")

    if isinstance(sample, dict):
        latency_ms = _normalize_latency_ms(sample.get("time"))
        if sample.get("error"):
            return "failed", latency_ms, {"error": str(sample["error"])}
        if latency_ms is not None:
            details = {key: value for key, value in sample.items() if value is not None and value != ""}
            return "passed", latency_ms, details
        return "failed", None, {"raw": sample}

    if isinstance(sample, list):
        latency_ms = next((_normalize_latency_ms(item) for item in sample if isinstance(item, (int, float))), None)
        message = next((str(item) for item in sample if isinstance(item, str) and item), None)
        status = "passed" if latency_ms is not None else "failed"
        details = {"raw": sample}
        if message:
            details["message"] = message
        return status, latency_ms, details

    return "failed", None, {"raw": sample}


def _parse_http_payload(node_payload: Any) -> tuple[str, float | None, int | None, dict[str, Any]]:
    sample = _unwrap_node_payload(node_payload)
    if sample is None:
        raise RuntimeError("Check-Host HTTP result is not ready yet.")

    if isinstance(sample, list):
        ok_flag = bool(sample[0]) if len(sample) > 0 else False
        latency_ms = _normalize_latency_ms(sample[1]) if len(sample) > 1 else None
        message = str(sample[2]) if len(sample) > 2 and sample[2] is not None else None
        http_status = _coerce_status_code(sample[3]) if len(sample) > 3 else None
        remote_ip = str(sample[4]) if len(sample) > 4 and sample[4] else None
        details: dict[str, Any] = {"raw": sample}
        if message:
            details["message"] = message
        if remote_ip:
            details["remote_ip"] = remote_ip
        status = "passed" if ok_flag and http_status is not None and 200 <= http_status < 400 else "failed"
        return status, latency_ms, http_status, details

    if isinstance(sample, dict):
        http_status = _coerce_status_code(sample.get("status"))
        latency_ms = _normalize_latency_ms(sample.get("time"))
        details = {key: value for key, value in sample.items() if value is not None and value != ""}
        status = "passed" if http_status is not None and 200 <= http_status < 400 else "failed"
        return status, latency_ms, http_status, details

    return "failed", None, None, {"raw": sample}


class CheckHostClient:
    def __init__(self, *, http_timeout: float, poll_attempts: int, poll_interval: float) -> None:
        self.http_timeout = http_timeout
        self.poll_attempts = poll_attempts
        self.poll_interval = poll_interval

    async def fetch_nodes(self) -> dict[str, CheckHostNode]:
        timeout = ClientTimeout(total=CHECK_HOST_NODE_CATALOG_TIMEOUT_SECONDS)
        async with ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{CHECK_HOST_BASE_URL}/nodes/hosts",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ProxyCraftGeoProbe/1.0",
                },
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Check-Host node catalog returned HTTP {response.status}")
                payload = await response.json(content_type=None)

        raw_nodes = payload.get("nodes") if isinstance(payload, dict) else payload
        if not isinstance(raw_nodes, dict) or not raw_nodes:
            raise RuntimeError("Check-Host node catalog payload is empty or malformed")

        return {
            node_id: _parse_node_metadata(node_id, raw)
            for node_id, raw in raw_nodes.items()
        }

    async def probe(self, *, target: GeoProbeTarget, region: Region, node: CheckHostNode) -> GeoProbeObservation:
        timeout = ClientTimeout(total=self.http_timeout)
        async with ClientSession(timeout=timeout) as session:
            request_id, permanent_link = await self._start_check(
                session=session,
                target=target,
                node_id=node.node_id,
            )
            node_payload = await self._poll_result(
                session=session,
                target=target,
                request_id=request_id,
                node_id=node.node_id,
            )

        if target.target_type == "tcp":
            status, latency_ms, details = _parse_tcp_payload(node_payload)
            details = {
                "request_id": request_id,
                "permanent_link": permanent_link,
                **details,
                **target.details,
            }
            if node.country_name:
                details.setdefault("probe_country_name", node.country_name)
            summary = (
                f"{target.product} is reachable from {REGION_LABELS[region]} via node {node.node_id}."
                if status == "passed"
                else f"{target.product} is not reachable from {REGION_LABELS[region]} via node {node.node_id}."
            )
            return GeoProbeObservation(
                product=target.product,
                target_type=target.target_type,
                endpoint=target.endpoint,
                probe_scope="external",
                probe_region=region,
                status=status,
                summary=summary,
                probe_node=node.node_id,
                probe_country=node.country_code or node.country_name,
                probe_city=node.city,
                probe_asn=node.asn,
                latency_ms=latency_ms,
                details=details,
            )

        status, latency_ms, http_status, details = _parse_http_payload(node_payload)
        details = {
            "request_id": request_id,
            "permanent_link": permanent_link,
            **details,
            **target.details,
        }
        if node.country_name:
            details.setdefault("probe_country_name", node.country_name)
        summary = (
            f"{target.product} returned HTTP {http_status} from {REGION_LABELS[region]} via node {node.node_id}."
            if status == "passed"
            else f"{target.product} failed HTTP probe from {REGION_LABELS[region]} via node {node.node_id}."
        )
        return GeoProbeObservation(
            product=target.product,
            target_type=target.target_type,
            endpoint=target.endpoint,
            probe_scope="external",
            probe_region=region,
            status=status,
            summary=summary,
            probe_node=node.node_id,
            probe_country=node.country_code or node.country_name,
            probe_city=node.city,
            probe_asn=node.asn,
            latency_ms=latency_ms,
            http_status=http_status,
            details=details,
        )

    async def _start_check(
        self,
        *,
        session: ClientSession,
        target: GeoProbeTarget,
        node_id: str,
    ) -> tuple[str, str | None]:
        endpoint = f"{CHECK_HOST_BASE_URL}/check-{target.target_type}"
        async with session.get(
            endpoint,
            params={"host": target.endpoint, "node": node_id},
            headers={
                "Accept": "application/json",
                "User-Agent": "ProxyCraftGeoProbe/1.0",
            },
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Check-Host {target.target_type} start returned HTTP {response.status} for {target.endpoint}"
                )
            payload = await response.json(content_type=None)

        request_id = payload.get("request_id")
        if not request_id:
            raise RuntimeError(f"Check-Host {target.target_type} start response has no request_id")
        return str(request_id), payload.get("permanent_link")

    async def _poll_result(
        self,
        *,
        session: ClientSession,
        target: GeoProbeTarget,
        request_id: str,
        node_id: str,
    ) -> Any:
        endpoint = f"{CHECK_HOST_BASE_URL}/check-result/{request_id}"
        for attempt in range(1, self.poll_attempts + 1):
            async with session.get(
                endpoint,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ProxyCraftGeoProbe/1.0",
                },
            ) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Check-Host result poll returned HTTP {response.status} for {target.endpoint}"
                    )
                payload = await response.json(content_type=None)

            node_payload = payload.get(node_id)
            if node_payload is not None:
                return node_payload

            if attempt < self.poll_attempts:
                await asyncio.sleep(self.poll_interval)

        raise RuntimeError(
            f"Check-Host result for {target.product} on node {node_id} did not become ready in time"
        )


def _select_node_for_region(region: Region, nodes: dict[str, CheckHostNode]) -> CheckHostNode | None:
    overrides = preferred_nodes(region)
    if overrides:
        for node_id in overrides:
            if node_id in nodes:
                return nodes[node_id]
        return CheckHostNode(node_id=overrides[0])

    candidates = [
        node for node in nodes.values()
        if node.country_code and node.country_code.upper() in REGION_COUNTRY_PRIORITY[region]
    ]
    if not candidates:
        return None

    priority = {country: index for index, country in enumerate(REGION_COUNTRY_PRIORITY[region])}
    candidates.sort(
        key=lambda node: (
            priority.get((node.country_code or "").upper(), 999),
            node.city or "",
            node.node_id,
        )
    )
    return candidates[0]


async def _persist_observation(db: Database, run_id: int, observation: GeoProbeObservation) -> None:
    async with db.session() as session:
        await GeoProbeResult.create(
            session=session,
            run_id=run_id,
            probe_scope=observation.probe_scope,
            probe_region=observation.probe_region,
            probe_node=observation.probe_node,
            probe_country=observation.probe_country,
            probe_city=observation.probe_city,
            probe_asn=observation.probe_asn,
            product=observation.product,
            target_type=observation.target_type,
            endpoint=observation.endpoint,
            status=observation.status,
            latency_ms=observation.latency_ms,
            http_status=observation.http_status,
            details=observation.details,
        )


async def _create_run(
    db: Database,
    *,
    trigger: str,
    details: dict[str, Any],
) -> GeoProbeRun:
    async with db.session() as session:
        return await GeoProbeRun.create(session=session, trigger=trigger, details=details)


async def _finish_run(
    db: Database,
    *,
    run_id: int,
    status: str,
    summary: str,
    details: dict[str, Any],
) -> GeoProbeRun | None:
    async with db.session() as session:
        return await GeoProbeRun.update_status(
            session=session,
            run_id=run_id,
            status=status,
            summary=summary,
            details=details,
        )


async def _resolve_targets(
    *,
    db: Database,
    product_filter: str,
) -> list[GeoProbeTarget]:
    config = load_config()
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

    targets: list[GeoProbeTarget] = []

    if product_filter in {"all", "mtproto"} and config.shop.MTPROTO_ENABLED:
        fixture = await resolve_mtproto_fixture(db=db)
        if fixture:
            link = await mtproto_service.get_link_for_subscription(fixture)
            if link:
                host, port, _ = parse_mtproto_endpoint(link)
                targets.append(
                    GeoProbeTarget(
                        key="mtproto",
                        product="mtproto",
                        region_scope=config.shop.MTPROTO_LOCATION,
                        target_type="tcp",
                        endpoint=f"{host}:{port}",
                        details={
                            "subscription_id": fixture.id,
                            "location": config.shop.MTPROTO_LOCATION,
                            "public_link": link,
                        },
                    )
                )

    if product_filter in {"all", "whatsapp"} and config.shop.WHATSAPP_ENABLED:
        fixture = await resolve_whatsapp_fixture(db=db)
        if fixture:
            connection = await whatsapp_service.get_connection_info_for_subscription(fixture)
            if connection:
                host, port = connection
                targets.append(
                    GeoProbeTarget(
                        key="whatsapp",
                        product="whatsapp",
                        region_scope=config.shop.WHATSAPP_LOCATION,
                        target_type="tcp",
                        endpoint=f"{host}:{port}",
                        details={
                            "subscription_id": fixture.id,
                            "location": config.shop.WHATSAPP_LOCATION,
                            "port": port,
                        },
                    )
                )

    if product_filter in {"all", "vpn"}:
        await server_pool.sync_servers()
        for spec in get_fixture_specs(product="vpn"):
            resolved = await resolve_vpn_fixture(db=db, vpn_service=vpn_service, spec=spec)
            if not resolved:
                continue
            subscription, _client_data = resolved
            key = await vpn_service.get_key_for_subscription(subscription)
            if not key:
                continue
            targets.append(
                GeoProbeTarget(
                    key=spec.key,
                    product=spec.key,
                    region_scope=spec.location or "unknown",
                    target_type="http",
                    endpoint=key,
                    details={
                        "subscription_id": subscription.id,
                        "location": spec.location,
                        "vpn_profile_slug": spec.vpn_profile_slug,
                    },
                )
            )

    return targets


def _build_summary(observations: list[GeoProbeObservation]) -> tuple[str, dict[str, Any], int]:
    passed = sum(1 for observation in observations if observation.status == "passed")
    warnings = sum(1 for observation in observations if observation.status == "warning")
    failed = sum(1 for observation in observations if observation.status == "failed")
    skipped = sum(1 for observation in observations if observation.status == "skipped")

    overall_status = "failed" if failed else "warning" if warnings else "passed"
    summary = (
        f"Geo probes completed: {passed} passed, {warnings} warnings, "
        f"{failed} failed, {skipped} skipped."
    )
    exit_code = 1 if failed else 0
    details = {
        "counts": {
            "passed": passed,
            "warning": warnings,
            "failed": failed,
            "skipped": skipped,
        },
        "products": sorted({observation.product for observation in observations}),
        "regions": sorted({observation.probe_region for observation in observations}),
    }
    return overall_status, details | {"summary": summary}, exit_code


def _print_human_summary(observations: list[GeoProbeObservation]) -> None:
    for observation in observations:
        line = (
            f"[{observation.status.upper()}] {observation.product} "
            f"[{observation.probe_region}] {observation.summary}"
        )
        if observation.endpoint:
            line += f" | endpoint={observation.endpoint}"
        if observation.probe_node:
            line += f" | node={observation.probe_node}"
        print(line)


def _build_notification_text(
    observations: list[GeoProbeObservation],
    context: dict[str, str | None],
) -> str:
    failures = [observation for observation in observations if observation.status == "failed"]
    warnings = [observation for observation in observations if observation.status == "warning"]
    icon = "🚨" if failures else "⚠️"
    title = "ProxyCraft geo-probes failed" if failures else "ProxyCraft geo-probe warnings"

    lines = [f"{icon} <b>{title}</b>"]
    if context.get("sha"):
        lines.append(f"Commit: <code>{context['sha'][:7]}</code>")
    if context.get("run_url"):
        lines.append(f'<a href="{context["run_url"]}">GitHub Actions run</a>')

    if failures:
        lines.append("")
        lines.append("<b>Failures</b>")
        for item in failures:
            lines.append(
                f"• <b>{item.product}</b> [{item.probe_region}] "
                f"{item.summary}"
            )

    if warnings:
        lines.append("")
        lines.append("<b>Warnings</b>")
        for item in warnings:
            lines.append(
                f"• <b>{item.product}</b> [{item.probe_region}] "
                f"{item.summary}"
            )

    return "\n".join(lines)


async def _maybe_notify_admins(
    *,
    observations: list[GeoProbeObservation],
    notify: bool,
    notify_warnings: bool,
) -> None:
    if not notify:
        return

    failures = [observation for observation in observations if observation.status == "failed"]
    warnings = [observation for observation in observations if observation.status == "warning"]
    if not failures and not (notify_warnings and warnings):
        return

    config = load_config()
    if not config.bot.ADMINS:
        logger.warning("BOT_ADMINS is empty, geo-probe alert delivery skipped.")
        return

    bot = Bot(
        token=config.bot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    try:
        message = _build_notification_text(observations, github_context())
        for chat_id in config.bot.ADMINS:
            try:
                await asyncio.wait_for(
                    bot.send_message(chat_id=chat_id, text=message),
                    timeout=NOTIFICATION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "Geo-probe alert delivery to %s exceeded %.1fs and was skipped.",
                    chat_id,
                    NOTIFICATION_TIMEOUT_SECONDS,
                )
            except Exception as exception:  # noqa: BLE001
                logger.warning("Geo-probe alert delivery to %s failed: %s", chat_id, exception)
    finally:
        await bot.session.close()


async def run_geo_probes(
    *,
    trigger: str,
    product_filter: str,
    notify: bool,
    notify_warnings: bool,
) -> tuple[list[GeoProbeObservation], int]:
    config = load_config()
    db = Database(config.database)
    await db.initialize()

    http_timeout = normalize_timeout("GEO_PROBE_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT)
    poll_attempts = normalize_attempts("GEO_PROBE_POLL_ATTEMPTS", CHECK_HOST_RESULT_POLL_ATTEMPTS)
    poll_interval = normalize_timeout("GEO_PROBE_POLL_INTERVAL", CHECK_HOST_RESULT_POLL_INTERVAL_SECONDS)
    fixture_timeout = normalize_timeout("GEO_PROBE_FIXTURE_TIMEOUT", FIXTURE_PROVISION_TIMEOUT_SECONDS)

    observations: list[GeoProbeObservation] = []
    run_record = await _create_run(
        db,
        trigger=trigger,
        details={
            "product_filter": product_filter,
            "notify": notify,
            "notify_warnings": notify_warnings,
        },
    )

    try:
        try:
            fixture_results = await asyncio.wait_for(
                provision_smoke_fixtures(),
                timeout=fixture_timeout,
            )
        except TimeoutError:
            fixture_results = []
            observations.append(
                GeoProbeObservation(
                    product="all",
                    target_type="http",
                    endpoint="fixtures",
                    probe_scope="fixture",
                    probe_region="global",
                    status="failed",
                    summary=(
                        "Smoke fixture provisioning for geo probes exceeded "
                        f"{fixture_timeout:.0f}s and was aborted."
                    ),
                    details={"timeout_seconds": fixture_timeout},
                )
            )
        else:
            for result in fixture_results:
                if result.status in {"ready", "passed"}:
                    continue
                observations.append(
                    GeoProbeObservation(
                        product=result.key,
                        target_type="http",
                        endpoint="fixtures",
                        probe_scope="fixture",
                        probe_region="global",
                        status="warning" if result.status == "warning" else result.status,
                        summary=result.summary,
                        details={
                            "product": result.product,
                            "user_tg_id": result.user_tg_id,
                            "subscription_id": result.subscription_id,
                            **(result.details or {}),
                        },
                    )
                )

        targets = await _resolve_targets(db=db, product_filter=product_filter)
        if not targets:
            observations.append(
                GeoProbeObservation(
                    product=product_filter,
                    target_type="http",
                    endpoint="n/a",
                    probe_scope="external",
                    probe_region="global",
                    status="skipped",
                    summary="No enabled public targets were resolved for geo probes.",
                )
            )

        probe_client = CheckHostClient(
            http_timeout=http_timeout,
            poll_attempts=poll_attempts,
            poll_interval=poll_interval,
        )

        node_catalog_error: str | None = None
        try:
            nodes = await probe_client.fetch_nodes()
        except Exception as exception:  # noqa: BLE001
            nodes = {}
            node_catalog_error = str(exception)
            logger.warning("Check-Host node catalog is unavailable: %s", exception)

        for target in targets:
            for region in REGION_COUNTRY_PRIORITY:
                node = _select_node_for_region(region, nodes)
                if not node:
                    observations.append(
                        GeoProbeObservation(
                            product=target.product,
                            target_type=target.target_type,
                            endpoint=target.endpoint,
                            probe_scope="external",
                            probe_region=region,
                            status="warning",
                            summary=(
                                f"No Check-Host node is available for {REGION_LABELS[region]}."
                            ),
                            details={
                                **target.details,
                                "region_scope": target.region_scope,
                                "node_catalog_error": node_catalog_error,
                            },
                        )
                    )
                    continue

                try:
                    observation = await probe_client.probe(
                        target=target,
                        region=region,
                        node=node,
                    )
                except Exception as exception:  # noqa: BLE001
                    observation = GeoProbeObservation(
                        product=target.product,
                        target_type=target.target_type,
                        endpoint=target.endpoint,
                        probe_scope="external",
                        probe_region=region,
                        status="failed",
                        summary=(
                            f"{target.product} probe from {REGION_LABELS[region]} failed: {exception}"
                        ),
                        probe_node=node.node_id,
                        probe_country=node.country_code or node.country_name,
                        probe_city=node.city,
                        probe_asn=node.asn,
                        details={
                            **target.details,
                            "region_scope": target.region_scope,
                            "reason": str(exception),
                            "node_catalog_error": node_catalog_error,
                        },
                    )
                else:
                    observation.details.setdefault("region_scope", target.region_scope)

                observations.append(observation)

        for observation in observations:
            await _persist_observation(db, run_record.id, observation)

        overall_status, summary_details, exit_code = _build_summary(observations)
        await _finish_run(
            db,
            run_id=run_record.id,
            status=overall_status,
            summary=summary_details["summary"],
            details=summary_details,
        )
        await _maybe_notify_admins(
            observations=observations,
            notify=notify,
            notify_warnings=notify_warnings,
        )
        return observations, exit_code
    except Exception as exception:  # noqa: BLE001
        await _finish_run(
            db,
            run_id=run_record.id,
            status="failed",
            summary=f"Geo probes aborted: {exception}",
            details={"reason": str(exception)},
        )
        raise
    finally:
        await db.close()


def main() -> None:
    args = parse_args()
    configure_logging()

    try:
        observations, exit_code = asyncio.run(
            run_geo_probes(
                trigger=args.trigger,
                product_filter=args.product,
                notify=args.notify,
                notify_warnings=args.notify_warnings,
            )
        )
    except KeyboardInterrupt:
        raise SystemExit(130) from None

    _print_human_summary(observations)
    if args.json:
        print(json.dumps([asdict(observation) for observation in observations], ensure_ascii=False, indent=2))

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
