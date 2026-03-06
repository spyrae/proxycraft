from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product_catalog import ProductCatalog, VpnProfile
    from .server_pool import ServerPoolService

import logging

from py3xui import Client, Inbound
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ClientData
from app.bot.utils.network import extract_base_url
from app.bot.utils.time import (
    add_days_to_timestamp,
    days_to_timestamp,
    get_current_timestamp,
)
from app.config import Config
from app.db.models import Promocode, User

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
        location = user.server.location if user.server else None
        return self._resolve_vpn_profile(user, location)

    def get_available_profiles(self, location: str | None) -> list[VpnProfile]:
        if not self.catalog or not location:
            return []
        return self.catalog.get_vpn_profiles(location=location)

    async def is_client_exists(self, user: User) -> Client | None:
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return None

        client = await self.server_pool_service.execute_api_call(
            connection,
            lambda: connection.api.client.get_by_email(str(user.tg_id)),
        )

        if client:
            logger.debug(f"Client {user.tg_id} exists on server {connection.server.name}.")
        else:
            logger.critical(f"Client {user.tg_id} not found on server {connection.server.name}.")

        return client

    async def get_limit_ip(self, user: User, client: Client) -> int | None:
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return None

        try:
            inbounds: list[Inbound] = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.inbound.get_list(),
            )
        except Exception as exception:
            logger.error(f"Failed to fetch inbounds: {exception}")
            return None

        for inbound in inbounds:
            for inbound_client in inbound.settings.clients:
                if inbound_client.email == client.email:
                    logger.debug(f"Client {client.email} limit ip: {inbound_client.limit_ip}")
                    return inbound_client.limit_ip

        logger.critical(f"Client {client.email} not found in inbounds.")
        return None

    async def get_client_data(self, user: User) -> ClientData | None:
        logger.debug(f"Starting to retrieve client data for {user.tg_id}.")

        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return None

        try:
            client = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.get_by_email(str(user.tg_id)),
            )

            if not client:
                logger.critical(
                    f"Client {user.tg_id} not found on server {connection.server.name}."
                )
                return None

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
            logger.debug(f"Successfully retrieved client data for {user.tg_id}: {client_data}.")
            return client_data
        except Exception as exception:
            logger.error(f"Error retrieving client data for {user.tg_id}: {exception}")
            return None

    async def get_key(self, user: User) -> str | None:
        async with self.session() as session:
            user = await User.get(session=session, tg_id=user.tg_id)

        if not user.server_id:
            logger.debug(f"Server ID for user {user.tg_id} not found.")
            return None

        subscription = extract_base_url(
            url=user.server.subscription_host or user.server.host,
            port=user.server.subscription_port or self.config.xui.SUBSCRIPTION_PORT,
            path=user.server.subscription_path or self.config.xui.SUBSCRIPTION_PATH,
        )
        key = f"{subscription}{user.vpn_id}"
        logger.debug(f"Fetched key for {user.tg_id}: {key}.")
        return key

    async def create_client(
        self,
        user: User,
        devices: int,
        duration: int,
        enable: bool = True,
        flow: str | None = None,
        total_gb: int = 0,
        inbound_id: int = 1,
        location: str | None = None,
    ) -> bool:
        logger.info(f"Creating new client {user.tg_id} | {devices} devices {duration} days.")

        await self.server_pool_service.assign_server_to_user(user, location=location)
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return False

        selected_profile = self._resolve_vpn_profile(user, connection.server.location)
        client_flow = flow
        if client_flow is None:
            client_flow = (
                (selected_profile.client_flow if selected_profile else None)
                or connection.server.client_flow
                or self.config.xui.CLIENT_FLOW
            )

        new_client = Client(
            email=str(user.tg_id),
            enable=enable,
            id=user.vpn_id,
            expiry_time=days_to_timestamp(duration),
            flow=client_flow,
            limit_ip=devices,
            sub_id=user.vpn_id,
            total_gb=total_gb,
        )
        inbound_id = await self.server_pool_service.get_inbound_id(
            connection,
            remark=selected_profile.inbound_remark if selected_profile else None,
            allow_fallback=selected_profile is None,
        )
        if inbound_id is None:
            logger.error(
                "Failed to resolve inbound for user %s on %s.",
                user.tg_id,
                connection.server.name,
            )
            return False

        try:
            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.add(inbound_id=inbound_id, clients=[new_client]),
            )
            await self._persist_vpn_profile(user, selected_profile)
            logger.info(f"Successfully created client for {user.tg_id}")
            return True
        except Exception as exception:
            logger.error(f"Error creating client for {user.tg_id}: {exception}")
            return False

    async def update_client(
        self,
        user: User,
        devices: int,
        duration: int,
        replace_devices: bool = False,
        replace_duration: bool = False,
        enable: bool = True,
        flow: str | None = None,
        total_gb: int = 0,
    ) -> bool:
        logger.info(f"Updating client {user.tg_id} | {devices} devices {duration} days.")
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return False

        try:
            client = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.get_by_email(str(user.tg_id)),
            )

            if client is None:
                logger.critical(f"Client {user.tg_id} not found for update.")
                return False

            if not replace_devices:
                current_device_limit = await self.get_limit_ip(user=user, client=client)
                devices = current_device_limit + devices

            current_time = get_current_timestamp()

            if not replace_duration:
                expiry_time_to_use = max(client.expiry_time, current_time)
            else:
                expiry_time_to_use = current_time

            expiry_time = add_days_to_timestamp(timestamp=expiry_time_to_use, days=duration)

            selected_profile = self._resolve_vpn_profile(user, connection.server.location)
            client_flow = flow
            if client_flow is None:
                client_flow = (
                    (selected_profile.client_flow if selected_profile else None)
                    or connection.server.client_flow
                    or self.config.xui.CLIENT_FLOW
                )

            client.enable = enable
            client.id = user.vpn_id
            client.expiry_time = expiry_time
            client.flow = client_flow
            client.limit_ip = devices
            client.sub_id = user.vpn_id
            client.total_gb = total_gb

            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.update(client_uuid=client.id, client=client),
            )
            await self._persist_vpn_profile(user, selected_profile)
            logger.info(f"Client {user.tg_id} updated successfully.")
            return True
        except Exception as exception:
            logger.error(f"Error updating client {user.tg_id}: {exception}")
            return False

    async def create_subscription(self, user: User, devices: int, duration: int, location: str | None = None) -> bool:
        if not await self.is_client_exists(user):
            return await self.create_client(user=user, devices=devices, duration=duration, location=location)
        return False

    async def extend_subscription(self, user: User, devices: int, duration: int) -> bool:
        return await self.update_client(
            user=user,
            devices=devices,
            duration=duration,
            replace_devices=True,
        )

    async def change_subscription(self, user: User, devices: int, duration: int) -> bool:
        if await self.is_client_exists(user):
            return await self.update_client(
                user,
                devices,
                duration,
                replace_devices=True,
                replace_duration=True,
            )
        return False

    async def process_bonus_days(self, user: User, duration: int, devices: int) -> bool:
        if await self.is_client_exists(user):
            updated = await self.update_client(user=user, devices=0, duration=duration)
            if updated:
                logger.info(f"Updated client {user.tg_id} with additional {duration} days(-s).")
                return True
        else:
            created = await self.create_client(user=user, devices=devices, duration=duration)
            if created:
                logger.info(f"Created client {user.tg_id} with additional {duration} days(-s)")
                return True

        return False

    async def change_operator(self, user: User, new_operator: str) -> bool:
        """Legacy wrapper: move client to another Amsterdam profile."""
        return await self.change_vpn_profile(user, new_operator)

    async def change_vpn_profile(self, user: User, new_profile_slug: str) -> bool:
        connection = await self.server_pool_service.get_connection(user)
        if not connection:
            return False

        current_profile = self._resolve_vpn_profile(user, connection.server.location)
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

        client_data = await self.get_client_data(user)
        if not client_data:
            return False

        old_inbound_id = await self.server_pool_service.get_inbound_id(
            connection,
            remark=current_profile.inbound_remark if current_profile else None,
            allow_fallback=current_profile is None,
        )
        if old_inbound_id is None:
            return False

        new_inbound_id = await self.server_pool_service.get_inbound_id(
            connection,
            remark=target_profile.inbound_remark,
            allow_fallback=False,
        )
        if new_inbound_id is None:
            return False

        new_flow = (
            target_profile.client_flow
            or connection.server.client_flow
            or self.config.xui.CLIENT_FLOW
        )

        try:
            client = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.get_by_email(str(user.tg_id)),
            )
            if client is None:
                logger.error(f"Client {user.tg_id} not found while changing VPN profile.")
                return False

            limit_ip = client_data._max_devices if client_data._max_devices != -1 else 0

            if old_inbound_id == new_inbound_id:
                client.flow = new_flow
                await self.server_pool_service.execute_api_call(
                    connection,
                    lambda: connection.api.client.update(client_uuid=client.id, client=client),
                )
                await self._persist_vpn_profile(user, target_profile)
                logger.info(
                    "Updated VPN profile flow for user %s (%s -> %s).",
                    user.tg_id,
                    current_profile.slug if current_profile else "default",
                    target_profile.slug,
                )
                return True

            # Create the replacement client first. 3X-UI can reject deleting the
            # last client from an inbound, so "delete then add" is not reliable.
            # This order also avoids a transient window without an active client.
            new_client = Client(
                email=str(user.tg_id),
                enable=True,
                id=user.vpn_id,
                expiry_time=client_data._expiry_time,
                flow=new_flow,
                limit_ip=limit_ip,
                sub_id=user.vpn_id,
                total_gb=0,
            )
            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.add(inbound_id=new_inbound_id, clients=[new_client]),
            )

            try:
                await self.server_pool_service.execute_api_call(
                    connection,
                    lambda: connection.api.client.delete(old_inbound_id, user.vpn_id),
                )
            except Exception:
                logger.exception(
                    "Failed to delete old inbound client for user %s after creating replacement "
                    "in inbound %s. Rolling back the new client.",
                    user.tg_id,
                    new_inbound_id,
                )
                try:
                    await self.server_pool_service.execute_api_call(
                        connection,
                        lambda: connection.api.client.delete(new_inbound_id, user.vpn_id),
                    )
                except Exception:
                    logger.exception(
                        "Rollback failed while removing replacement client for user %s from "
                        "inbound %s.",
                        user.tg_id,
                        new_inbound_id,
                    )
                return False

            await self._persist_vpn_profile(user, target_profile)
            logger.info(
                "User %s moved from inbound %s to %s (profile: %s -> %s)",
                user.tg_id,
                old_inbound_id,
                new_inbound_id,
                current_profile.slug if current_profile else "default",
                target_profile.slug,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to change VPN profile for user {user.tg_id}: {e}")
            return False

    async def disable_client(self, user: User) -> bool:
        """Disable a client in 3X-UI (set enable=False)."""
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return False

        try:
            client = await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.get_by_email(str(user.tg_id)),
            )

            if client is None:
                logger.warning(f"Client {user.tg_id} not found for disabling.")
                return False

            client.enable = False
            await self.server_pool_service.execute_api_call(
                connection,
                lambda: connection.api.client.update(client_uuid=client.id, client=client),
            )
            logger.info(f"Client {user.tg_id} disabled successfully.")
            return True
        except Exception as e:
            logger.error(f"Error disabling client {user.tg_id}: {e}")
            return False

    async def get_all_clients_data(self) -> dict[str, ClientData]:
        """Fetch all clients from all servers in batch (1 API call per server).

        Returns:
            dict mapping email (tg_id as string) to ClientData.
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
                    result[email] = ClientData(
                        max_devices=max_devices,
                        traffic_total=traffic_total,
                        traffic_remaining=traffic_remaining,
                        traffic_used=traffic_used,
                        traffic_up=client.up,
                        traffic_down=client.down,
                        expiry_time=expiry_time,
                    )

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
