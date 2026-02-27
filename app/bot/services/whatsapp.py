import logging
import subprocess
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Config
from app.db.models import WhatsAppSubscription

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self, config: Config, session_factory: async_sessionmaker) -> None:
        self.config = config
        self.session_factory = session_factory
        self.host = config.shop.WHATSAPP_HOST
        self.port_min = config.shop.WHATSAPP_PORT_MIN
        self.port_max = config.shop.WHATSAPP_PORT_MAX
        self.haproxy_config_path = config.shop.WHATSAPP_HAPROXY_CONFIG_PATH
        logger.info("WhatsApp Service initialized.")

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
                # User already has a subscription — try to reactivate
                existing = await WhatsAppSubscription.get_by_user(session, user_tg_id)
                if existing:
                    await WhatsAppSubscription.update_expiry(session, user_tg_id, expires_at)
                    port = existing.port
                else:
                    logger.error(f"Failed to create WhatsApp subscription for user {user_tg_id}")
                    return None

        await self._regenerate_and_reload()
        logger.info(f"WhatsApp activated for user {user_tg_id}, port {port}, expires {expires_at}")
        return port

    async def extend(self, user_tg_id: int, duration_days: int) -> bool:
        """Extend an existing subscription by adding days."""
        async with self.session_factory() as session:
            sub = await WhatsAppSubscription.get_by_user(session, user_tg_id)
            if not sub:
                logger.warning(f"No WhatsApp subscription to extend for user {user_tg_id}")
                return False

            now = datetime.utcnow()
            base = sub.expires_at if sub.expires_at > now else now
            new_expires = base + timedelta(days=duration_days)
            await WhatsAppSubscription.update_expiry(session, user_tg_id, new_expires)

        logger.info(f"WhatsApp extended for user {user_tg_id}, new expiry {new_expires}")
        return True

    async def deactivate(self, user_tg_id: int) -> bool:
        """Deactivate subscription, regenerate HAProxy config, reload."""
        async with self.session_factory() as session:
            result = await WhatsAppSubscription.deactivate(session, user_tg_id)

        if result:
            await self._regenerate_and_reload()
            logger.info(f"WhatsApp deactivated for user {user_tg_id}")
        return result

    async def get_connection_info(self, user_tg_id: int) -> tuple[str, int] | None:
        """Return (host, port) for the user."""
        async with self.session_factory() as session:
            sub = await WhatsAppSubscription.get_by_user(session, user_tg_id)
            if not sub or not sub.is_active:
                return None
        return (self.host, sub.port)

    async def is_active(self, user_tg_id: int) -> bool:
        """Check if user has an active, non-expired subscription."""
        async with self.session_factory() as session:
            sub = await WhatsAppSubscription.get_by_user(session, user_tg_id)
            if not sub or not sub.is_active:
                return False
            return sub.expires_at > datetime.utcnow()

    async def get_subscription(self, user_tg_id: int) -> WhatsAppSubscription | None:
        """Get subscription data."""
        async with self.session_factory() as session:
            return await WhatsAppSubscription.get_by_user(session, user_tg_id)

    async def is_trial_available(self, user_tg_id: int) -> bool:
        """Check if user can use the free trial."""
        async with self.session_factory() as session:
            sub = await WhatsAppSubscription.get_by_user(session, user_tg_id)
            if sub and sub.is_trial_used:
                return False
        return True

    async def cleanup_expired(self) -> int:
        """Deactivate all expired subscriptions, regenerate config. Returns count."""
        count = 0
        async with self.session_factory() as session:
            expired = await WhatsAppSubscription.get_expired_active(session)
            for sub in expired:
                await WhatsAppSubscription.deactivate(session, sub.user_tg_id)
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
        self._write_haproxy_config(config_content)
        self._reload_haproxy()

    def _generate_haproxy_config(self, active_subs: list[WhatsAppSubscription]) -> str:
        """Generate the full HAProxy config with per-user frontends."""
        lines = [
            "global",
            "    log stdout format raw local0",
            "    maxconn 4096",
            "",
            "defaults",
            "    mode tcp",
            "    timeout connect 10s",
            "    timeout client 1h",
            "    timeout server 1h",
            "",
            "backend whatsapp",
            "    server wa1 g.whatsapp.net:443",
            "",
        ]

        if active_subs:
            lines.append("# Per-user frontends")
            for sub in sorted(active_subs, key=lambda s: s.port):
                lines.append(f"frontend user_{sub.user_tg_id}")
                lines.append(f"    bind *:{sub.port}")
                lines.append("    default_backend whatsapp")
                lines.append("")

        return "\n".join(lines)

    def _write_haproxy_config(self, content: str) -> None:
        """Write HAProxy config file."""
        try:
            with open(self.haproxy_config_path, "w") as f:
                f.write(content)
            logger.debug("HAProxy config written successfully")
        except Exception as e:
            logger.error(f"Failed to write HAProxy config: {e}")

    def _reload_haproxy(self) -> None:
        """Send HUP signal to HAProxy container for graceful reload."""
        try:
            result = subprocess.run(
                ["docker", "kill", "-s", "HUP", "vpncraft-whatsapp"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("HAProxy reloaded (HUP)")
            else:
                logger.error(f"Failed to reload HAProxy: {result.stderr}")
        except Exception as e:
            logger.error(f"Error sending HUP to whatsapp container: {e}")
