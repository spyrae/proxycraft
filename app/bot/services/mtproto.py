import logging
import os
import re
import secrets
import signal
import subprocess
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Config
from app.db.models import MTProtoSubscription

logger = logging.getLogger(__name__)


class MTProtoService:
    def __init__(self, config: Config, session_factory: async_sessionmaker) -> None:
        self.config = config
        self.session_factory = session_factory
        self.host = config.shop.MTPROTO_HOST
        self.port = config.shop.MTPROTO_PORT
        self.config_path = config.shop.MTPROTO_CONFIG_PATH
        logger.info("MTProto Service initialized.")

    async def activate(self, user_tg_id: int, duration_days: int, is_trial: bool = False) -> str | None:
        """Generate a secret, save to DB, update config, reload proxy."""
        secret = secrets.token_hex(16)
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        async with self.session_factory() as session:
            sub = await MTProtoSubscription.create(
                session=session,
                user_tg_id=user_tg_id,
                secret=secret,
                expires_at=expires_at,
                is_trial_used=is_trial,
            )
            if not sub:
                # User already has a subscription — try to reactivate
                existing = await MTProtoSubscription.get_by_user(session, user_tg_id)
                if existing:
                    await MTProtoSubscription.update_expiry(session, user_tg_id, expires_at)
                    secret = existing.secret
                else:
                    logger.error(f"Failed to create MTProto subscription for user {user_tg_id}")
                    return None

        self._update_config_add_user(user_tg_id, secret)
        self._reload_proxy()
        logger.info(f"MTProto activated for user {user_tg_id}, expires {expires_at}")
        return secret

    async def extend(self, user_tg_id: int, duration_days: int) -> bool:
        """Extend an existing subscription by adding days."""
        async with self.session_factory() as session:
            sub = await MTProtoSubscription.get_by_user(session, user_tg_id)
            if not sub:
                logger.warning(f"No MTProto subscription to extend for user {user_tg_id}")
                return False

            now = datetime.utcnow()
            base = sub.expires_at if sub.expires_at > now else now
            new_expires = base + timedelta(days=duration_days)
            await MTProtoSubscription.update_expiry(session, user_tg_id, new_expires)

        logger.info(f"MTProto extended for user {user_tg_id}, new expiry {new_expires}")
        return True

    async def deactivate(self, user_tg_id: int) -> bool:
        """Remove secret from config, reload proxy, mark inactive."""
        async with self.session_factory() as session:
            result = await MTProtoSubscription.deactivate(session, user_tg_id)

        if result:
            self._update_config_remove_user(user_tg_id)
            self._reload_proxy()
            logger.info(f"MTProto deactivated for user {user_tg_id}")
        return result

    async def get_link(self, user_tg_id: int) -> str | None:
        """Return tg://proxy link for the user."""
        async with self.session_factory() as session:
            sub = await MTProtoSubscription.get_by_user(session, user_tg_id)
            if not sub or not sub.is_active:
                return None

        # FakeTLS prefix "ee" + secret
        return f"tg://proxy?server={self.host}&port={self.port}&secret=ee{sub.secret}"

    async def is_active(self, user_tg_id: int) -> bool:
        """Check if user has an active, non-expired subscription."""
        async with self.session_factory() as session:
            sub = await MTProtoSubscription.get_by_user(session, user_tg_id)
            if not sub or not sub.is_active:
                return False
            return sub.expires_at > datetime.utcnow()

    async def get_subscription(self, user_tg_id: int) -> MTProtoSubscription | None:
        """Get subscription data."""
        async with self.session_factory() as session:
            return await MTProtoSubscription.get_by_user(session, user_tg_id)

    async def is_trial_available(self, user_tg_id: int) -> bool:
        """Check if user can use the free trial."""
        async with self.session_factory() as session:
            sub = await MTProtoSubscription.get_by_user(session, user_tg_id)
            if sub and sub.is_trial_used:
                return False
        return True

    async def cleanup_expired(self) -> int:
        """Deactivate all expired subscriptions. Returns count of cleaned up."""
        count = 0
        async with self.session_factory() as session:
            expired = await MTProtoSubscription.get_expired_active(session)
            for sub in expired:
                await MTProtoSubscription.deactivate(session, sub.user_tg_id)
                self._update_config_remove_user(sub.user_tg_id)
                count += 1

        if count > 0:
            self._reload_proxy()
            logger.info(f"MTProto cleanup: deactivated {count} expired subscriptions")
        return count

    def get_price(self, duration_days: int) -> int | None:
        """Get price in RUB for given duration."""
        prices = {
            30: self.config.shop.MTPROTO_PRICE_30,
            90: self.config.shop.MTPROTO_PRICE_90,
            180: self.config.shop.MTPROTO_PRICE_180,
            365: self.config.shop.MTPROTO_PRICE_365,
        }
        return prices.get(duration_days)

    def get_price_stars(self, duration_days: int) -> int | None:
        """Get price in Telegram Stars for given duration (1 star ~ 1.8 RUB)."""
        rub_price = self.get_price(duration_days)
        if rub_price is None:
            return None
        return max(1, round(rub_price / 1.8))

    # --- Config management ---

    def _read_config(self) -> str:
        """Read mtprotoproxy config.py."""
        try:
            with open(self.config_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"MTProto config not found: {self.config_path}")
            return ""

    def _write_config(self, content: str) -> None:
        """Write mtprotoproxy config.py."""
        try:
            with open(self.config_path, "w") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write MTProto config: {e}")

    def _update_config_add_user(self, user_tg_id: int, secret: str) -> None:
        """Add user entry to USERS dict in config.py."""
        content = self._read_config()
        if not content:
            return

        key = f"tg_{user_tg_id}"
        entry = f'    "{key}": "{secret}",'

        # Check if user already exists
        if f'"{key}"' in content:
            # Update existing entry
            content = re.sub(
                rf'(\s*"{key}"\s*:\s*")[^"]*(")',
                rf'\g<1>{secret}\2',
                content,
            )
        else:
            # Add new entry before closing brace of USERS dict
            content = re.sub(
                r"(USERS\s*=\s*\{)(.*?)(})",
                rf"\1\2{entry}\n\3",
                content,
                flags=re.DOTALL,
            )

        self._write_config(content)

    def _update_config_remove_user(self, user_tg_id: int) -> None:
        """Remove user entry from USERS dict in config.py."""
        content = self._read_config()
        if not content:
            return

        key = f"tg_{user_tg_id}"
        # Remove the line containing this user's entry
        content = re.sub(rf'\s*"{key}"\s*:\s*"[^"]*"\s*,?\n?', "\n", content)

        self._write_config(content)

    def _reload_proxy(self) -> None:
        """Send SIGUSR2 to mtprotoproxy container for hot reload."""
        try:
            result = subprocess.run(
                ["docker", "kill", "-s", "SIGUSR2", "vpncraft-mtproto"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("MTProto proxy reloaded (SIGUSR2)")
            else:
                logger.error(f"Failed to reload MTProto proxy: {result.stderr}")
        except Exception as e:
            logger.error(f"Error sending SIGUSR2 to mtproto container: {e}")
