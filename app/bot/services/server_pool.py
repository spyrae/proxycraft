import asyncio
import logging
from dataclasses import dataclass

from httpx import HTTPStatusError
from py3xui import AsyncApi
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Config
from app.db.models import Server, User

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    server: Server
    api: AsyncApi


class ServerPoolService:
    def __init__(self, config: Config, session: async_sessionmaker) -> None:
        self.config = config
        self.session = session
        self._servers: dict[int, Connection] = {}
        self._sync_lock = asyncio.Lock()
        logger.info("Server Pool Service initialized.")

    def _create_api(self, server: Server) -> AsyncApi:
        return AsyncApi(
            host=server.host,
            username=self.config.xui.USERNAME,
            password=self.config.xui.PASSWORD,
            token=self.config.xui.TOKEN,
            logger=logging.getLogger(f"xui_{server.name}"),
        )

    async def _add_server(self, server: Server) -> None:
        if server.id not in self._servers:
            api = self._create_api(server)
            try:
                await api.login()
                server.online = True
                server_conn = Connection(server=server, api=api)
                self._servers[server.id] = server_conn
                logger.info(f"Server {server.name} ({server.host}) added to pool successfully.")
            except Exception as exception:
                server.online = False
                logger.error(f"Failed to add server {server.name} ({server.host}): {exception}")

            async with self.session() as session:
                await Server.update(session=session, name=server.name, online=server.online)

    async def _relogin(self, connection: Connection) -> bool:
        server = connection.server
        logger.info(f"Re-login to server {server.name} ({server.host})...")
        api = self._create_api(server)
        try:
            await api.login()
            connection.api = api
            server.online = True
            logger.info(f"Re-login to server {server.name} successful.")
            return True
        except Exception as exception:
            server.online = False
            logger.error(f"Re-login to server {server.name} failed: {exception}")
            return False

    def _remove_server(self, server: Server) -> None:
        if server.id in self._servers:
            try:
                del self._servers[server.id]
            except Exception as exception:
                logger.error(f"Failed to remove server {server.name}: {exception}")

    async def refresh_server(self, server: Server) -> None:
        if server.id in self._servers:
            self._remove_server(server)

        await self._add_server(server)
        logger.info(f"Server {server.name} reinitialized successfully.")

    async def get_inbound_id(
        self,
        connection: Connection,
        remark: str | None = None,
        allow_fallback: bool = True,
    ) -> int | None:
        try:
            inbounds = await self._api_call_with_relogin(
                connection, lambda: connection.api.inbound.get_list()
            )
        except Exception as exception:
            logger.error(f"Failed to fetch inbounds for {connection.server.name}: {exception}")
            return None

        target_remark = remark or connection.server.inbound_remark or self.config.xui.INBOUND_REMARK
        if target_remark:
            for inbound in inbounds:
                if inbound.remark == target_remark:
                    logger.debug(f"Found inbound by remark '{target_remark}': id={inbound.id}")
                    return inbound.id
            if not allow_fallback:
                logger.error(
                    "Inbound with remark '%s' not found on %s and fallback is disabled.",
                    target_remark,
                    connection.server.name,
                )
                return None
            logger.warning(f"Inbound with remark '{target_remark}' not found, falling back to first.")

        if not inbounds:
            logger.error("No inbounds available on server %s.", connection.server.name)
            return None

        return inbounds[0].id

    async def get_connection(self, user: User) -> Connection | None:
        if not user.server_id:
            logger.debug(f"User {user.tg_id} not assigned to any server.")
            return None

        connection = self._servers.get(user.server_id)

        if not connection:
            available_servers = list(self._servers.keys())
            logger.warning(
                f"Server {user.server_id} not found in pool. "
                f"User assigned server: {user.server_id}, "
                f"Available servers in pool: {available_servers}"
            )

            async with self.session() as session:
                server = await Server.get_by_id(session=session, id=user.server_id)

            if server:
                logger.info(f"Server {server.name} ({server.host}) found in database, recovering to pool...")
                await self._add_server(server)
                connection = self._servers.get(user.server_id)
                if connection:
                    return connection
                logger.error(f"Failed to recover server {server.name} to pool.")
            else:
                logger.error(f"Server {user.server_id} not found in database.")

            return None

        async with self.session() as session:
            server = await Server.get_by_id(session=session, id=user.server_id)

        connection.server = server
        return connection

    async def _api_call_with_relogin(self, connection: Connection, coro_factory):
        """Execute an API call with automatic re-login on auth failure.

        coro_factory is a callable that returns a coroutine, e.g.:
            lambda: connection.api.client.get_by_email(email)
        """
        try:
            return await coro_factory()
        except (HTTPStatusError, ValueError) as exc:
            err_msg = str(exc).lower()
            if "401" in err_msg or "unauthorized" in err_msg or "login" in err_msg or "session" in err_msg:
                logger.warning(f"Auth error on {connection.server.name}, attempting re-login: {exc}")
                if await self._relogin(connection):
                    return await coro_factory()
            raise

    async def execute_api_call(self, connection: Connection, coro_factory):
        return await self._api_call_with_relogin(connection, coro_factory)

    async def sync_servers(self, force_refresh: bool = False) -> None:
        async with self._sync_lock:
            async with self.session() as session:
                db_servers = await Server.get_all(session)

            if not db_servers and not self._servers:
                logger.warning("No servers found in the database.")
                return

            db_server_map = {server.id: server for server in db_servers}

            for server_id in list(self._servers.keys()):
                if server_id not in db_server_map:
                    self._remove_server(self._servers[server_id].server)

            for server in db_servers:
                connection = self._servers.get(server.id)
                if connection is None:
                    await self._add_server(server)
                    continue

                connection.server = server

                if force_refresh:
                    await self.refresh_server(server)

            logger.info(
                "Sync complete. Currently active servers: %s (force_refresh=%s)",
                len(self._servers),
                force_refresh,
            )

    async def assign_server_to_user(self, user: User, location: str | None = None) -> None:
        async with self.session() as session:
            server = await self.get_available_server(location=location)
            user.server_id = server.id
            await User.update(session=session, tg_id=user.tg_id, server_id=server.id)

    async def get_available_server(self, location: str | None = None) -> Server | None:
        await self.sync_servers()

        candidates = [conn.server for conn in self._servers.values()]

        if location:
            location_filtered = [s for s in candidates if s.location == location]
            if location_filtered:
                candidates = location_filtered
            else:
                logger.warning(f"No servers found for location '{location}', using all servers")

        servers_with_free_slots = [
            s for s in candidates
            if s.current_clients < s.max_clients
        ]

        if servers_with_free_slots:
            server = sorted(servers_with_free_slots, key=lambda s: s.current_clients)[0]
            logger.debug(
                f"Found server with free slots: {server.name} "
                f"(clients: {server.current_clients}/{server.max_clients})"
            )
            return server

        if candidates:
            server = sorted(candidates, key=lambda s: s.current_clients)[0]
            logger.warning(
                f"No servers with free slots. Using least loaded server: {server.name} "
                f"(clients: {server.current_clients}/{server.max_clients})"
            )
            return server

        logger.critical("No available servers found in pool")
        return None

    async def get_locations(self) -> list[dict]:
        await self.sync_servers()
        locations: dict[str, bool] = {}
        for conn in self._servers.values():
            loc = conn.server.location or "Unknown"
            if loc not in locations:
                locations[loc] = conn.server.online
            elif conn.server.online:
                locations[loc] = True
        return [{"name": name, "available": available} for name, available in locations.items()]
