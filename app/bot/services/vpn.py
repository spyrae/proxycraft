from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode

if TYPE_CHECKING:
    from .product_catalog import ProductCatalog, VpnProfile
    from .server_pool import ServerPoolService

import logging

from py3xui import Client, Inbound
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ClientData
from app.bot.utils.network import extract_base_url
from app.bot.utils.time import (
    add_days_to_timestamp,
    days_to_timestamp,
    get_current_timestamp,
)
from app.config import Config
from app.db.models import Promocode, User, VPNSubscription

logger = logging.getLogger(__name__)


class VPNService:
    def __init__(
        self,
        config: Config,
        session: async_sessionmaker,
        server_pool_service: ServerPoolService,
        catalog: ProductCatalog | None = None,
    ) -> None:
        self.config = config
        self.session = session
        self.server_pool_service = server_pool_service
        self.catalog = catalog
        logger.info("VPN Service initialized.")

    @staticmethod
    def _build_client_email(user_tg_id: int, vpn_id: str) -> str:
        return f"{user_tg_id}-{vpn_id[:8]}"

    async def list_subscriptions(self, user: User) -> list[VPNSubscription]:
        async with self.session() as session:
            return await VPNSubscription.list_by_user(session=session, user_tg_id=user.tg_id)

    async def has_any_subscription(self, user_tg_id: int) -> bool:
        async with self.session() as session:
            return await VPNSubscription.has_any(session=session, user_tg_id=user_tg_id)

    async def get_primary_subscription(self, user: User) -> VPNSubscription | None:
        async with self.session() as session:
            if user.vpn_id:
                primary = await VPNSubscription.get_by_vpn_id(session=session, vpn_id=user.vpn_id)
                if primary:
                    return primary

            return await VPNSubscription.get_latest_by_user(session=session, user_tg_id=user.tg_id)

    async def get_subscription(self, subscription_id: int) -> VPNSubscription | None:
        async with self.session() as session:
            return await VPNSubscription.get_by_id(session=session, subscription_id=subscription_id)

    def _resolve_vpn_profile_for_subscription(self, subscription: VPNSubscription) -> VpnProfile | None:
        if not self.catalog:
            return None

        location = subscription.server.location if subscription.server else None
        return self.catalog.resolve_vpn_profile(
            location=location,
            profile_slug=subscription.vpn_profile_slug,
            legacy_slug=None,
        )

    async def _persist_subscription_profile(
        self,
        subscription: VPNSubscription,
        profile: VpnProfile | None,
    ) -> None:
        profile_slug = profile.slug if profile else None

        async with self.session() as session:
            await VPNSubscription.update(
                session=session,
                subscription_id=subscription.id,
                vpn_profile_slug=profile_slug,
            )

        subscription.vpn_profile_slug = profile_slug

    async def _persist_vpn_profile(self, user: User, profile: VpnProfile | None) -> None:
        profile_slug = profile.slug if profile else None
        legacy_operator = None
        if profile and profile.kind == "operator" and profile.legacy_slugs:
            legacy_operator = profile.legacy_slugs[0]

        async with self.session() as session:
            await User.update(
                session=session,
                tg_id=user.tg_id,
                vpn_profile_slug=profile_slug,
                operator=legacy_operator,
            )

        user.vpn_profile_slug = profile_slug
        user.operator = legacy_operator

    def _resolve_vpn_profile(
        self,
        user: User,
        location: str | None,
    ) -> VpnProfile | None:
        if not self.catalog:
            return None

        return self.catalog.resolve_vpn_profile(
            location=location,
            profile_slug=user.vpn_profile_slug,
            legacy_slug=user.operator,
        )

    def get_current_profile(self, user: User) -> VpnProfile | None:
        if user.vpn_profile_slug and user.server and user.server.location:
            return self._resolve_vpn_profile(user, user.server.location)
        return None

    def get_profile_for_subscription(self, subscription: VPNSubscription) -> VpnProfile | None:
        return self._resolve_vpn_profile_for_subscription(subscription)

    def get_available_profiles(self, location: str | None) -> list[VpnProfile]:
        if not self.catalog or not location:
            return []
        return self.catalog.get_vpn_profiles(location=location)

    async def _get_subscription_connection(self, subscription: VPNSubscription):
        return await self.server_pool_service.get_connection_for_server_id(
            subscription.server_id,
            user_label=f"vpn_subscription {subscription.id}",
        )

    async def _find_client_for_subscription(
        self,
        subscription: VPNSubscription,
    ) -> tuple[Client, Inbound] | None:
        connection = await self._get_subscription_connection(subscription)
        if not connection:
            return None

        try:
            inbounds: list[Inbound] = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.inbound.get_list(),
            )
        except Exception as exception:
            logger.error(
                "Failed to fetch inbounds for vpn subscription %s: %s",
                subscription.id,
                exception,
            )
            return None

        for inbound in inbounds:
            for inbound_client in inbound.settings.clients:
                if (
                    inbound_client.id == subscription.vpn_id
                    or inbound_client.email == subscription.client_email
                ):
                    return inbound_client, inbound

        logger.warning(
            "Client for vpn subscription %s not found on server %s.",
            subscription.id,
            connection.server.name if connection else subscription.server_id,
        )
        return None

    async def is_client_exists(self, user: User) -> Client | None:
        subscription = await self.get_primary_subscription(user)
        if not subscription:
            return None

        found = await self._find_client_for_subscription(subscription)
        return found[0] if found else None

    async def get_limit_ip(self, user: User, client: Client) -> int | None:
        subscription = await self.get_primary_subscription(user)
        if not subscription:
            return None

        found = await self._find_client_for_subscription(subscription)
        if not found:
            return None

        inbound_client, _ = found
        logger.debug("Client %s limit ip: %s", inbound_client.email, inbound_client.limit_ip)
        return inbound_client.limit_ip

    async def get_client_data_for_subscription(
        self,
        subscription: VPNSubscription,
    ) -> ClientData | None:
        logger.debug("Starting to retrieve client data for vpn subscription %s.", subscription.id)

        try:
            found = await self._find_client_for_subscription(subscription)
            if not found:
                return None

            client, _ = found
            limit_ip = client.limit_ip
            max_devices = -1 if limit_ip == 0 else limit_ip
            traffic_total = client.total
            expiry_time = -1 if client.expiry_time == 0 else client.expiry_time

            if traffic_total <= 0:
                traffic_remaining = -1
                traffic_total = -1
            else:
                traffic_remaining = client.total - (client.up + client.down)

            traffic_used = client.up + client.down
            client_data = ClientData(
                max_devices=max_devices,
                traffic_total=traffic_total,
                traffic_remaining=traffic_remaining,
                traffic_used=traffic_used,
                traffic_up=client.up,
                traffic_down=client.down,
                expiry_time=expiry_time,
            )
            logger.debug(
                "Successfully retrieved client data for vpn subscription %s: %s.",
                subscription.id,
                client_data,
            )
            return client_data
        except Exception as exception:
            logger.error(
                "Error retrieving client data for vpn subscription %s: %s",
                subscription.id,
                exception,
            )
            return None

    async def get_client_data(self, user: User) -> ClientData | None:
        subscription = await self.get_primary_subscription(user)
        if not subscription:
            return None
        return await self.get_client_data_for_subscription(subscription)

    async def get_client_data_for_subscriptions(
        self,
        subscriptions: list[VPNSubscription],
    ) -> dict[int, ClientData | None]:
        if not subscriptions:
            return {}

        try:
            all_clients = await self.get_all_clients_data()
        except Exception as exception:
            logger.error(
                "Error retrieving batch client data for vpn subscriptions: %s",
                exception,
            )
            return {subscription.id: None for subscription in subscriptions}

        result: dict[int, ClientData | None] = {}
        for subscription in subscriptions:
            result[subscription.id] = (
                all_clients.get(subscription.vpn_id)
                or all_clients.get(subscription.client_email)
            )

        return result

    async def get_key_for_subscription(self, subscription: VPNSubscription) -> str | None:
        """Generate a VLESS URI for the subscription's current profile inbound."""
        subscription_id = subscription.id

        try:
            server = subscription.server
        except DetachedInstanceError:
            server = None

        if not server:
            async with self.session() as session:
                subscription = await VPNSubscription.get_by_id(session=session, subscription_id=subscription_id)
            if not subscription:
                logger.debug("VPN subscription %s no longer exists while generating key.", subscription_id)
                return None

            server = subscription.server
            if not server:
                logger.debug("Server is not attached to vpn subscription %s.", subscription_id)
                return None

        connection = await self.server_pool_service.get_connection_for_server_id(
            server.id, user_label=f"sub {subscription_id}",
        )
        if not connection:
            return self._build_subscription_url(subscription, server)

        selected_profile = self._resolve_vpn_profile_for_subscription(subscription)
        target_remark = selected_profile.inbound_remark if selected_profile else None

        try:
            inbounds = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.inbound.get_list(),
            )
        except Exception as e:
            logger.warning("Failed to fetch inbounds for key generation (sub %s): %s", subscription_id, e)
            return self._build_subscription_url(subscription, server)

        inbound = None
        if target_remark:
            inbound = next((ib for ib in inbounds if ib.remark == target_remark), None)
        if not inbound:
            inbound = next((ib for ib in inbounds if ib.protocol == "vless"), None)

        if not inbound:
            return self._build_subscription_url(subscription, server)

        public_host = server.subscription_host or server.host
        vless_uri = self._build_vless_uri(
            uuid=subscription.vpn_id,
            host=public_host,
            inbound=inbound,
            remark=f"{inbound.remark}-{subscription.client_email}",
        )
        logger.debug("Generated VLESS key for sub %s: %s", subscription_id, vless_uri[:80])
        return vless_uri

    def _build_subscription_url(self, subscription: VPNSubscription, server) -> str:
        """Fallback: legacy subscription panel URL."""
        base = extract_base_url(
            url=server.subscription_host or server.host,
            port=server.subscription_port or self.config.xui.SUBSCRIPTION_PORT,
            path=server.subscription_path or self.config.xui.SUBSCRIPTION_PATH,
        )
        return f"{base}{subscription.vpn_id}"

    @staticmethod
    def _build_vless_uri(
        uuid: str,
        host: str,
        inbound: Inbound,
        remark: str,
    ) -> str:
        """Build a VLESS share URI from inbound data."""
        ss = inbound.stream_settings
        params: dict[str, str] = {}

        params["type"] = ss.network or "tcp"

        # Security & Reality settings
        params["security"] = ss.security or "none"
        if ss.security == "reality" and ss.reality_settings:
            rs = ss.reality_settings
            server_names = rs.get("serverNames", [])
            short_ids = rs.get("shortIds", [])
            settings = rs.get("settings", {})

            params["pbk"] = settings.get("publicKey", "")
            params["fp"] = settings.get("fingerprint", "chrome")
            if server_names:
                params["sni"] = random.choice(server_names)
            if short_ids:
                params["sid"] = random.choice(short_ids)

            spider_x = settings.get("spiderX", "/")
            if spider_x:
                # Generate random path like 3X-UI does
                import string
                rand_path = "".join(random.choices(string.ascii_letters + string.digits, k=16))
                params["spx"] = spider_x.rstrip("/") + "/" + rand_path if spider_x != "/" else "/" + rand_path

        # Flow (for Reality+TCP)
        flow = ""
        for client in inbound.settings.clients:
            if client.id == uuid:
                flow = client.flow or ""
                break
        if flow:
            params["flow"] = flow

        # Transport-specific params
        if ss.network == "ws":
            ws = ss.tcp_settings if not hasattr(ss, "ws_settings") else {}
            # WS path from external proxy or defaults
            if ss.external_proxy:
                ep = ss.external_proxy[0]
                params["host"] = ep.get("dest", host)
                # For CDN, connect to CDN domain, not direct IP
                host = ep.get("dest", host)

        elif ss.network == "xhttp":
            pass  # XHTTP uses Reality settings above

        port = inbound.port
        encoded_remark = quote(remark, safe="")
        query = urlencode(params, safe="/:@")
        return f"vless://{uuid}@{host}:{port}?{query}#{encoded_remark}"

    async def get_key(self, user: User) -> str | None:
        subscription = await self.get_primary_subscription(user)
        if not subscription:
            return None
        return await self.get_key_for_subscription(subscription)

    async def _update_user_primary_subscription(
        self,
        user: User,
        subscription: VPNSubscription,
    ) -> None:
        async with self.session() as session:
            await User.update(
                session=session,
                tg_id=user.tg_id,
                vpn_id=subscription.vpn_id,
                server_id=subscription.server_id,
                vpn_cancelled_at=subscription.cancelled_at,
                vpn_profile_slug=subscription.vpn_profile_slug,
            )

        user.vpn_id = subscription.vpn_id
        user.server_id = subscription.server_id
        user.vpn_cancelled_at = subscription.cancelled_at
        user.vpn_profile_slug = subscription.vpn_profile_slug

    async def _create_client_for_subscription(
        self,
        user: User,
        subscription: VPNSubscription,
        devices: int,
        duration: int,
        enable: bool = True,
        flow: str | None = None,
        total_gb: int = 0,
    ) -> bool:
        connection = await self._get_subscription_connection(subscription)
        if not connection:
            return False

        selected_profile = self._resolve_vpn_profile_for_subscription(subscription)
        client_flow = flow
        if client_flow is None:
            profile_flow = selected_profile.client_flow if selected_profile else None
            if profile_flow is not None:
                client_flow = profile_flow
            else:
                client_flow = connection.server.client_flow or self.config.xui.CLIENT_FLOW

        new_client = Client(
            email=subscription.client_email,
            enable=enable,
            id=subscription.vpn_id,
            expiry_time=days_to_timestamp(duration),
            flow=client_flow,
            limit_ip=devices,
            sub_id=subscription.vpn_id,
            total_gb=total_gb,
        )
        inbound_id = await self.server_pool_service.get_inbound_id(
            connection,
            remark=selected_profile.inbound_remark if selected_profile else None,
            allow_fallback=selected_profile is None,
        )
        if inbound_id is None:
            logger.error(
                "Failed to resolve inbound for vpn subscription %s on %s.",
                subscription.id,
                connection.server.name,
            )
            return False

        try:
            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.add(inbound_id=inbound_id, clients=[new_client]),
            )
        except Exception as exception:
            if "Duplicate email" in str(exception) or "duplicate" in str(exception).lower():
                logger.warning(
                    "Duplicate client %s in 3X-UI for subscription %s, removing all stale copies.",
                    subscription.client_email,
                    subscription.id,
                )
                await self._remove_stale_clients_by_email(connection, subscription.client_email)
                try:
                    await self.server_pool_service.execute_api_call(
                        connection,
                        lambda: connection.api.client.add(inbound_id=inbound_id, clients=[new_client]),
                    )
                except Exception as retry_exc:
                    logger.error("Retry after duplicate removal failed for subscription %s: %s", subscription.id, retry_exc)
                    return False
            else:
                logger.error("Error creating client for vpn subscription %s: %s", subscription.id, exception)
                return False

        try:
            await self._persist_subscription_profile(subscription, selected_profile)
            await self._persist_vpn_profile(user, selected_profile)
            await self._update_user_primary_subscription(user, subscription)
            logger.info("Successfully created client for vpn subscription %s", subscription.id)
        except Exception as exception:
            logger.error("Error persisting subscription data for %s: %s", subscription.id, exception)
            return False
        return True

    async def _remove_stale_clients_by_email(self, connection, email: str) -> int:
        """Find and delete ALL clients with given email across all inbounds on a server."""
        removed = 0
        try:
            inbounds: list[Inbound] = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.inbound.get_list(),
            )
        except Exception as exc:
            logger.error("Failed to list inbounds for stale client cleanup: %s", exc)
            return 0

        for inbound in inbounds:
            for client in inbound.settings.clients:
                if client.email == email:
                    try:
                        ib_id = inbound.id
                        c_uuid = client.id
                        await self.server_pool_service.execute_api_call(
                            connection,
                            lambda _ib=ib_id, _cu=c_uuid: connection.api.client.delete(
                                inbound_id=_ib, client_uuid=_cu,
                            ),
                        )
                        removed += 1
                        logger.info("Removed stale client email=%s uuid=%s from inbound %s", email, client.id, inbound.id)
                    except Exception as del_exc:
                        logger.warning("Failed to remove stale client %s from inbound %s: %s", client.id, inbound.id, del_exc)
        return removed

    async def _update_subscription_client(
        self,
        user: User,
        subscription: VPNSubscription,
        devices: int,
        duration: int,
        replace_devices: bool = False,
        replace_duration: bool = False,
        enable: bool = True,
        flow: str | None = None,
        total_gb: int = 0,
    ) -> bool:
        connection = await self._get_subscription_connection(subscription)
        if not connection:
            return False

        try:
            found = await self._find_client_for_subscription(subscription)
            if not found:
                logger.critical("VPN client %s not found for update.", subscription.id)
                return False

            client, _ = found

            if replace_devices:
                next_devices = devices
            else:
                current_device_limit = 0 if client.limit_ip == 0 else client.limit_ip
                next_devices = current_device_limit + devices

            current_time = get_current_timestamp()
            if not replace_duration:
                expiry_time_to_use = max(client.expiry_time, current_time)
            else:
                expiry_time_to_use = current_time

            expiry_time = add_days_to_timestamp(timestamp=expiry_time_to_use, days=duration)

            selected_profile = self._resolve_vpn_profile_for_subscription(subscription)
            client_flow = flow
            if client_flow is None:
                profile_flow = selected_profile.client_flow if selected_profile else None
                if profile_flow is not None:
                    client_flow = profile_flow
                else:
                    client_flow = connection.server.client_flow or self.config.xui.CLIENT_FLOW

            client.enable = enable
            client.id = subscription.vpn_id
            client.email = subscription.client_email
            client.expiry_time = expiry_time
            client.flow = client_flow
            client.limit_ip = next_devices
            client.sub_id = subscription.vpn_id
            client.total_gb = total_gb

            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.update(client_uuid=client.id, client=client),
            )
            await self._persist_subscription_profile(subscription, selected_profile)
            await self._persist_vpn_profile(user, selected_profile)
            async with self.session() as session:
                updated_subscription = await VPNSubscription.update(
                    session=session,
                    subscription_id=subscription.id,
                    devices=next_devices if next_devices > 0 else None,
                )
            if updated_subscription:
                subscription.devices = updated_subscription.devices
                subscription.vpn_profile_slug = updated_subscription.vpn_profile_slug
            logger.info("VPN client %s updated successfully.", subscription.id)
            return True
        except Exception as exception:
            logger.error("Error updating vpn subscription %s: %s", subscription.id, exception)
            return False

    async def create_subscription_instance(
        self,
        user: User,
        devices: int,
        duration: int,
        location: str | None = None,
    ) -> VPNSubscription | None:
        server = await self.server_pool_service.get_available_server(location=location)
        if not server:
            return None

        selected_profile = self._resolve_vpn_profile(user, server.location)
        has_existing = await self.has_any_subscription(user.tg_id)
        vpn_id = user.vpn_id if not has_existing else str(uuid.uuid4())
        client_email = str(user.tg_id) if not has_existing else self._build_client_email(user.tg_id, vpn_id)

        async with self.session() as session:
            subscription = await VPNSubscription.create(
                session=session,
                user_tg_id=user.tg_id,
                vpn_id=vpn_id,
                client_email=client_email,
                server_id=server.id,
                devices=devices,
                vpn_profile_slug=selected_profile.slug if selected_profile else None,
            )

        if not subscription:
            return None

        loaded_subscription = await self.get_subscription(subscription.id)
        if not loaded_subscription:
            logger.error(
                "Failed to reload vpn subscription %s after creation.",
                subscription.id,
            )
            async with self.session() as session:
                doomed = await VPNSubscription.get_by_id(session=session, subscription_id=subscription.id)
                if doomed:
                    await session.delete(doomed)
                    await session.commit()
            return None

        if not await self._create_client_for_subscription(
            user,
            loaded_subscription,
            devices=devices,
            duration=duration,
        ):
            async with self.session() as session:
                doomed = await VPNSubscription.get_by_id(session=session, subscription_id=subscription.id)
                if doomed:
                    await session.delete(doomed)
                    await session.commit()
            return None

        return loaded_subscription

    async def create_subscription(self, user: User, devices: int, duration: int, location: str | None = None) -> bool:
        subscription = await self.create_subscription_instance(
            user=user,
            devices=devices,
            duration=duration,
            location=location,
        )
        return subscription is not None

    async def extend_subscription(
        self,
        user: User,
        devices: int,
        duration: int,
        subscription_id: int | None = None,
    ) -> bool:
        subscription = (
            await self.get_subscription(subscription_id)
            if subscription_id is not None
            else await self.get_primary_subscription(user)
        )
        if not subscription:
            return False

        return await self._update_subscription_client(
            user=user,
            subscription=subscription,
            devices=devices,
            duration=duration,
            replace_devices=True,
        )

    async def change_subscription(
        self,
        user: User,
        devices: int,
        duration: int,
        subscription_id: int | None = None,
    ) -> bool:
        subscription = (
            await self.get_subscription(subscription_id)
            if subscription_id is not None
            else await self.get_primary_subscription(user)
        )
        if not subscription:
            return False

        return await self._update_subscription_client(
            user=user,
            subscription=subscription,
            devices=devices,
            duration=duration,
            replace_devices=True,
            replace_duration=True,
        )

    async def process_bonus_days(self, user: User, duration: int, devices: int) -> bool:
        subscription = await self.get_primary_subscription(user)
        if subscription and await self._find_client_for_subscription(subscription):
            updated = await self._update_subscription_client(
                user=user,
                subscription=subscription,
                devices=0,
                duration=duration,
            )
            if updated:
                logger.info("Updated primary vpn subscription %s with additional %s days.", subscription.id, duration)
                return True
        else:
            created = await self.create_subscription(user=user, devices=devices, duration=duration)
            if created:
                logger.info("Created vpn subscription for %s with additional %s days.", user.tg_id, duration)
                return True

        return False

    async def change_operator(
        self,
        user: User,
        new_operator: str,
        subscription_id: int | None = None,
    ) -> bool:
        """Legacy wrapper: move client to another Amsterdam profile."""
        return await self.change_vpn_profile(
            user=user,
            new_profile_slug=new_operator,
            subscription_id=subscription_id,
        )

    async def change_vpn_profile(
        self,
        user: User,
        new_profile_slug: str,
        subscription_id: int | None = None,
    ) -> bool:
        subscription = (
            await self.get_subscription(subscription_id)
            if subscription_id is not None
            else await self.get_primary_subscription(user)
        )
        if not subscription:
            logger.error("Cannot change VPN profile: subscription not found.")
            return False

        connection = await self._get_subscription_connection(subscription)
        if not connection:
            return False

        current_profile = self._resolve_vpn_profile_for_subscription(subscription)
        target_profile = (
            self.catalog.get_vpn_profile(new_profile_slug, location=connection.server.location)
            if self.catalog
            else None
        )
        if not target_profile:
            logger.error(
                "VPN profile '%s' is not available for location %s.",
                new_profile_slug,
                connection.server.location,
            )
            return False

        is_primary = subscription.vpn_id == user.vpn_id
        if target_profile.client_flow is not None:
            new_flow = target_profile.client_flow
        else:
            new_flow = connection.server.client_flow or self.config.xui.CLIENT_FLOW

        try:
            inbounds = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.inbound.get_list(),
            )
            if not inbounds:
                logger.error("No inbounds available on server %s.", connection.server.name)
                return False

            def resolve_inbound_id(remark: str | None, *, allow_fallback: bool) -> int | None:
                target_remark = remark or connection.server.inbound_remark or self.config.xui.INBOUND_REMARK
                if target_remark:
                    for inbound in inbounds:
                        if inbound.remark == target_remark:
                            return inbound.id
                    if not allow_fallback:
                        logger.error(
                            "Inbound with remark '%s' not found on %s and fallback is disabled.",
                            target_remark,
                            connection.server.name,
                        )
                        return None
                return inbounds[0].id

            old_inbound_id = resolve_inbound_id(
                current_profile.inbound_remark if current_profile else None,
                allow_fallback=current_profile is None,
            )
            new_inbound_id = resolve_inbound_id(target_profile.inbound_remark, allow_fallback=False)
            if old_inbound_id is None or new_inbound_id is None:
                return False

            old_inbound = next((inbound for inbound in inbounds if inbound.id == old_inbound_id), None)
            new_inbound = next((inbound for inbound in inbounds if inbound.id == new_inbound_id), None)
            if old_inbound is None or new_inbound is None:
                logger.error(
                    "Failed to load inbounds for profile migration of user %s (%s -> %s).",
                    user.tg_id,
                    old_inbound_id,
                    new_inbound_id,
                )
                return False

            moved_client = next(
                (
                    existing
                    for existing in old_inbound.settings.clients
                    if existing.id == subscription.vpn_id or existing.email == subscription.client_email
                ),
                None,
            )
            if moved_client is None:
                logger.error(
                    "Client for vpn subscription %s not found while changing profile.",
                    subscription.id,
                )
                return False

            moved_client = moved_client.model_copy(deep=True)
            limit_ip = moved_client.limit_ip

            if old_inbound_id == new_inbound_id:
                moved_client.flow = new_flow
                await self.server_pool_service.execute_api_call(
                    connection,
                    lambda: connection.api.client.update(client_uuid=moved_client.id, client=moved_client),
                )
                await self._persist_subscription_profile(subscription, target_profile)
                if is_primary:
                    await self._persist_vpn_profile(user, target_profile)
                logger.info(
                    "Updated VPN profile flow for subscription %s (%s -> %s).",
                    subscription.id,
                    current_profile.slug if current_profile else "default",
                    target_profile.slug,
                )
                return True

            # Cross-inbound switch: COPY client to new inbound (keep in old too).
            # 3X-UI requires unique email per client_traffics, so we suffix
            # the email with the inbound id for copies.
            already_in_new = any(
                existing.id == subscription.vpn_id
                for existing in new_inbound.settings.clients
            )

            if not already_in_new:
                # Use unique email: base_email@inbound_id
                copy_email = f"{subscription.client_email}@{new_inbound_id}"
                copy_client = Client(
                    email=copy_email,
                    enable=True,
                    id=subscription.vpn_id,
                    expiry_time=moved_client.expiry_time,
                    flow=new_flow,
                    limit_ip=limit_ip,
                    sub_id=subscription.vpn_id,
                    total_gb=0,
                )

                try:
                    await self.server_pool_service.execute_api_call(
                        connection,
                        lambda: connection.api.client.add(
                            inbound_id=new_inbound_id, clients=[copy_client],
                        ),
                    )
                except Exception as e:
                    if "Duplicate" in str(e):
                        logger.info(
                            "Client already in inbound %s for subscription %s (duplicate).",
                            new_inbound_id, subscription.id,
                        )
                    else:
                        logger.exception(
                            "Failed to add client to inbound %s for subscription %s.",
                            new_inbound_id, subscription.id,
                        )
                        return False

            await self._persist_subscription_profile(subscription, target_profile)
            if is_primary:
                await self._persist_vpn_profile(user, target_profile)
            logger.info(
                "Subscription %s: added to inbound %s (profile: %s -> %s)",
                subscription.id,
                new_inbound_id,
                current_profile.slug if current_profile else "default",
                target_profile.slug,
            )
            return True
        except Exception as e:
            logger.error("Failed to change VPN profile for subscription %s: %s", subscription.id, e)
            return False

    async def disable_client(self, user: User, subscription_id: int | None = None) -> bool:
        """Disable a client in 3X-UI (set enable=False)."""
        subscription = (
            await self.get_subscription(subscription_id)
            if subscription_id is not None
            else await self.get_primary_subscription(user)
        )
        if not subscription:
            return False

        connection = await self._get_subscription_connection(subscription)

        if not connection:
            return False

        try:
            found = await self._find_client_for_subscription(subscription)
            if not found:
                logger.warning("Client for vpn subscription %s not found for disabling.", subscription.id)
                return False
            client, _ = found

            client.enable = False
            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.update(client_uuid=client.id, client=client),
            )
            logger.info("Client for vpn subscription %s disabled successfully.", subscription.id)
            return True
        except Exception as e:
            logger.error("Error disabling vpn subscription %s: %s", subscription.id, e)
            return False

    async def get_all_clients_data(self) -> dict[str, ClientData]:
        """Fetch all clients from all servers in batch (1 API call per server).

        Returns:
            dict mapping both client UUID and client email to ClientData.
        """
        result: dict[str, ClientData] = {}

        for server_id, connection in self.server_pool_service._servers.items():
            try:
                inbounds = await self.server_pool_service.execute_api_call(
                    connection,
                    lambda: connection.api.inbound.get_list(),
                )
            except Exception as e:
                logger.error(f"Failed to fetch inbounds from server {connection.server.name}: {e}")
                continue

            for inbound in inbounds:
                for client in inbound.settings.clients:
                    email = client.email
                    limit_ip = client.limit_ip
                    max_devices = -1 if limit_ip == 0 else limit_ip
                    traffic_total = client.total
                    expiry_time = -1 if client.expiry_time == 0 else client.expiry_time

                    if traffic_total <= 0:
                        traffic_remaining = -1
                        traffic_total = -1
                    else:
                        traffic_remaining = client.total - (client.up + client.down)

                    traffic_used = client.up + client.down
                    payload = ClientData(
                        max_devices=max_devices,
                        traffic_total=traffic_total,
                        traffic_remaining=traffic_remaining,
                        traffic_used=traffic_used,
                        traffic_up=client.up,
                        traffic_down=client.down,
                        expiry_time=expiry_time,
                    )
                    result[client.id] = payload
                    if email:
                        result[email] = payload

        logger.info(f"Batch fetched {len(result)} clients from {len(self.server_pool_service._servers)} servers.")
        return result

    async def activate_promocode(self, user: User, promocode: Promocode) -> bool:
        # TODO: consider moving to some 'promocode module services' with usage of vpn-service methods.

        async with self.session() as session:
            activated = await Promocode.set_activated(
                session=session,
                code=promocode.code,
                user_id=user.tg_id,
            )

        if not activated:
            logger.critical(f"Failed to activate promocode {promocode.code} for user {user.tg_id}.")
            return False

        logger.info(f"Begun applying promocode ({promocode.code}) to a client {user.tg_id}.")
        success = await self.process_bonus_days(
            user,
            duration=promocode.duration,
            devices=self.config.shop.BONUS_DEVICES_COUNT,
        )

        if success:
            return True

        async with self.session() as session:
            await Promocode.set_deactivated(session=session, code=promocode.code)

        logger.warning(f"Promocode {promocode.code} not activated due to failure.")
        return False
