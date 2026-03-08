import http.client
import json
import logging
import os
import socket
import tempfile
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Config
from app.db.models import WhatsAppSubscription

logger = logging.getLogger(__name__)

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
WHATSAPP_CONTAINER_NAME = "proxycraft-whatsapp"


class WhatsAppService:
    def __init__(self, config: Config, session_factory: async_sessionmaker) -> None:
        self.config = config
        self.session_factory = session_factory
        self.host = config.shop.WHATSAPP_HOST
        self.port_min = config.shop.WHATSAPP_PORT_MIN
        self.port_max = config.shop.WHATSAPP_PORT_MAX
        self.haproxy_config_path = config.shop.WHATSAPP_HAPROXY_CONFIG_PATH
        logger.info("WhatsApp Service initialized.")

    async def startup_sync(self) -> None:
        """Regenerate HAProxy config on bot startup to ensure all active subscriptions have frontends."""
        await self._regenerate_and_reload()
        logger.info("WhatsApp HAProxy config synced on startup.")

    async def activate(self, user_tg_id: int, duration_days: int, is_trial: bool = False) -> int | None:
        """Assign a port, save to DB, regenerate HAProxy config, reload. Returns port or None."""
        async with self.session_factory() as session:
            port = await WhatsAppSubscription.get_next_available_port(
                session, self.port_min, self.port_max
            )
            if port is None:
                logger.error(f"No available ports for WhatsApp user {user_tg_id}")
                return None

            expires_at = datetime.utcnow() + timedelta(days=duration_days)

            sub = await WhatsAppSubscription.create(
                session=session,
                user_tg_id=user_tg_id,
                port=port,
                expires_at=expires_at,
                is_trial_used=is_trial,
            )
            if not sub:
                logger.error(f"Failed to create WhatsApp subscription for user {user_tg_id}")
                return None

        await self._regenerate_and_reload()
        logger.info(f"WhatsApp activated for user {user_tg_id}, port {port}, expires {expires_at}")
        return port

    async def extend(
        self,
        user_tg_id: int,
        duration_days: int,
        subscription_id: int | None = None,
    ) -> bool:
        """Extend an existing subscription by adding days."""
        async with self.session_factory() as session:
            sub = (
                await WhatsAppSubscription.get_by_id(session, subscription_id)
                if subscription_id is not None
                else await WhatsAppSubscription.get_by_user(session, user_tg_id)
            )
            if not sub:
                logger.warning(f"No WhatsApp subscription to extend for user {user_tg_id}")
                return False

            now = datetime.utcnow()
            base = sub.expires_at if sub.expires_at > now else now
            new_expires = base + timedelta(days=duration_days)
            await WhatsAppSubscription.update_expiry(
                session,
                user_tg_id,
                new_expires,
                subscription_id=sub.id,
            )

        logger.info(f"WhatsApp extended for user {user_tg_id}, new expiry {new_expires}")
        return True

    async def deactivate(self, user_tg_id: int, subscription_id: int | None = None) -> bool:
        """Deactivate subscription, regenerate HAProxy config, reload."""
        async with self.session_factory() as session:
            sub = (
                await WhatsAppSubscription.get_by_id(session, subscription_id)
                if subscription_id is not None
                else await WhatsAppSubscription.get_by_user(session, user_tg_id)
            )
            if not sub:
                return False
            result = await WhatsAppSubscription.deactivate(
                session,
                user_tg_id,
                subscription_id=sub.id,
            )

        if result:
            await self._regenerate_and_reload()
            logger.info(f"WhatsApp deactivated for user {user_tg_id}")
        return result

    async def get_connection_info_for_subscription(
        self,
        subscription: WhatsAppSubscription,
    ) -> tuple[str, int] | None:
        if not subscription or not subscription.is_active:
            return None
        return (self.host, subscription.port)

    async def get_connection_info(
        self,
        user_tg_id: int,
        subscription_id: int | None = None,
    ) -> tuple[str, int] | None:
        """Return (host, port) for the user."""
        async with self.session_factory() as session:
            sub = (
                await WhatsAppSubscription.get_by_id(session, subscription_id)
                if subscription_id is not None
                else await WhatsAppSubscription.get_by_user(session, user_tg_id)
            )
            if not sub:
                return None
        return await self.get_connection_info_for_subscription(sub)

    async def is_active(self, user_tg_id: int) -> bool:
        """Check if user has an active, non-expired subscription."""
        async with self.session_factory() as session:
            subscriptions = await WhatsAppSubscription.list_by_user(session, user_tg_id)
        now = datetime.utcnow()
        return any(sub.is_active and sub.expires_at > now for sub in subscriptions)

    async def get_subscription(self, user_tg_id: int) -> WhatsAppSubscription | None:
        """Get subscription data."""
        async with self.session_factory() as session:
            return await WhatsAppSubscription.get_by_user(session, user_tg_id)

    async def get_subscription_by_id(self, subscription_id: int) -> WhatsAppSubscription | None:
        async with self.session_factory() as session:
            return await WhatsAppSubscription.get_by_id(session, subscription_id)

    async def list_subscriptions(self, user_tg_id: int) -> list[WhatsAppSubscription]:
        async with self.session_factory() as session:
            return await WhatsAppSubscription.list_by_user(session, user_tg_id)

    async def is_trial_available(self, user_tg_id: int) -> bool:
        """Check if user can use the free trial."""
        async with self.session_factory() as session:
            return not await WhatsAppSubscription.has_trial_used(session, user_tg_id)

    async def cleanup_expired(self) -> int:
        """Deactivate all expired subscriptions, regenerate config. Returns count."""
        count = 0
        async with self.session_factory() as session:
            expired = await WhatsAppSubscription.get_expired_active(session)
            for sub in expired:
                await WhatsAppSubscription.deactivate(
                    session,
                    sub.user_tg_id,
                    subscription_id=sub.id,
                )
                count += 1

        if count > 0:
            await self._regenerate_and_reload()
            logger.info(f"WhatsApp cleanup: deactivated {count} expired subscriptions")
        return count

    def get_price(self, duration_days: int) -> int | None:
        """Get price in RUB for given duration."""
        prices = {
            30: self.config.shop.WHATSAPP_PRICE_30,
            90: self.config.shop.WHATSAPP_PRICE_90,
            180: self.config.shop.WHATSAPP_PRICE_180,
            365: self.config.shop.WHATSAPP_PRICE_365,
        }
        return prices.get(duration_days)

    def get_price_stars(self, duration_days: int) -> int | None:
        """Get price in Telegram Stars for given duration (1 star ~ 1.8 RUB)."""
        rub_price = self.get_price(duration_days)
        if rub_price is None:
            return None
        return max(1, round(rub_price / 1.8))

    # --- HAProxy config management ---

    async def _regenerate_and_reload(self) -> None:
        """Regenerate the entire HAProxy config from active subscriptions and reload."""
        async with self.session_factory() as session:
            active_subs = await WhatsAppSubscription.get_all_active(session)

        config_content = self._generate_haproxy_config(active_subs)
        if not self._write_haproxy_config(config_content):
            logger.error("Skipping HAProxy reload because config write failed")
            return
        if not self._reload_haproxy():
            logger.error("HAProxy reload failed after config write")

    def _generate_haproxy_config(self, active_subs: list[WhatsAppSubscription]) -> str:
        """Generate the full HAProxy config matching the official WhatsApp proxy spec.

        Official WhatsApp proxy protocol:
        - Client connects with TLS → proxy terminates SSL → forwards to g.whatsapp.net:5222
        - PROXY protocol v1 header sent to backend (carries client's real IP)
        - Self-signed cert is fine (WhatsApp client accepts it)
        """
        ssl_cert_path = "/etc/haproxy/ssl/proxy.pem"

        lines = [
            "global",
            "    log stdout format raw local0",
            "    tune.bufsize 4096",
            "    maxconn 4096",
            "    ssl-server-verify none",
            "    user haproxy",
            "    group haproxy",
            "",
            "resolvers docker_dns",
            "    nameserver dns1 127.0.0.11:53",
            "    resolve_retries 3",
            "    timeout resolve 1s",
            "    timeout retry 1s",
            "    hold valid 30s",
            "",
            "defaults",
            "    mode tcp",
            "    timeout connect 5s",
            "    timeout client-fin 1s",
            "    timeout server-fin 1s",
            "    timeout client 200s",
            "    timeout server 200s",
            "    default-server inter 10s fastinter 1s downinter 3s error-limit 50",
            "",
            "# Chat backend: WhatsApp XMPP with PROXY protocol",
            "backend wa",
            "    default-server check inter 60000 observe layer4 send-proxy",
            f"    server wa1 g.whatsapp.net:5222 resolvers docker_dns resolve-prefer ipv4",
            "",
            "# Media backend: whatsapp.net (no PROXY protocol)",
            "backend wa_media",
            "    default-server check inter 60000 observe layer4",
            f"    server media1 whatsapp.net:443 resolvers docker_dns resolve-prefer ipv4",
            "",
            "# Shared media frontends (ports 587, 7777 — media upload/download)",
            "frontend media_587",
            "    bind *:587",
            "    default_backend wa_media",
            "",
            "frontend media_7777",
            "    bind *:7777",
            "    default_backend wa_media",
            "",
        ]

        if active_subs:
            lines.append("# Per-user chat frontends (SSL termination + forward to wa backend)")
            for sub in sorted(active_subs, key=lambda s: s.port):
                lines.append(f"frontend user_{sub.user_tg_id}")
                lines.append(f"    bind *:{sub.port} ssl crt {ssl_cert_path}")
                lines.append("    default_backend wa")
                lines.append("")

        return "\n".join(lines)

    def _write_haproxy_config(self, content: str) -> bool:
        """Write HAProxy config file atomically."""
        config_dir = os.path.dirname(self.haproxy_config_path)
        temp_path: str | None = None
        try:
            os.makedirs(config_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                dir=config_dir,
                prefix=".haproxy.",
                suffix=".cfg",
                delete=False,
            ) as f:
                f.write(content)
                temp_path = f.name
            os.replace(temp_path, self.haproxy_config_path)
            logger.debug("HAProxy config written successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to write HAProxy config: {e}")
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning(f"Failed to remove temp HAProxy config: {temp_path}")
            return False

    def _docker_request(self, method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn = http.client.HTTPConnection("localhost")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.connect(DOCKER_SOCKET_PATH)
            conn.sock = sock
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            response_body = response.read()
            return response.status, response_body
        finally:
            conn.close()

    def _reload_haproxy(self) -> bool:
        """Send HUP to the whatsapp container entrypoint.

        The container entrypoint validates the config before reloading HAProxy,
        so duplicating that validation here only adds another failure mode.
        """
        try:
            status, body = self._docker_request(
                "POST",
                f"/containers/{WHATSAPP_CONTAINER_NAME}/kill?signal=HUP",
            )
            if status == 204:
                logger.info("HAProxy reloaded (HUP via Docker socket)")
                return True

            logger.error(
                "Failed to reload HAProxy: HTTP %s — %s",
                status,
                body.decode(errors="replace"),
            )
            return False
        except FileNotFoundError:
            logger.error(f"Docker socket not found at {DOCKER_SOCKET_PATH}. Mount it in docker-compose.yml")
            return False
        except Exception as e:
            logger.error(f"Error sending HUP to whatsapp container: {e}")
            return False
