import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Config
from app.db.models.awg_peer import AWGPeer

logger = logging.getLogger(__name__)


class AmneziaWGService:
    """Manages AmneziaWG peers: key generation, config files, and Docker sync."""

    def __init__(self, config: Config, session_factory: async_sessionmaker) -> None:
        self.config = config
        self.session = session_factory
        self.awg = config.awg
        self._peers_dir = Path(self.awg.PEERS_DIR)

    @property
    def enabled(self) -> bool:
        return self.awg.ENABLED

    async def create_peer(self, vpn_subscription_id: int) -> AWGPeer | None:
        """Create a new AWG peer for a VPN subscription."""
        if not self.enabled:
            return None

        async with self.session() as session:
            existing = await AWGPeer.get_by_subscription(session, vpn_subscription_id)
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    await session.commit()
                    await self._write_peer_config(existing)
                    await self._sync_awg()
                return existing

            max_suffix = await AWGPeer.get_max_ip_suffix(session)
            next_suffix = max_suffix + 1
            if next_suffix > 254:
                logger.error("AWG subnet exhausted, cannot allocate IP for subscription %s", vpn_subscription_id)
                return None

            subnet_prefix = ".".join(self.awg.SUBNET.split(".")[:3])
            assigned_ip = f"{subnet_prefix}.{next_suffix}"

            private_key, public_key = await self._generate_keypair()
            preshared_key = await self._generate_preshared_key()

            peer = await AWGPeer.create(
                session=session,
                vpn_subscription_id=vpn_subscription_id,
                private_key=private_key,
                public_key=public_key,
                preshared_key=preshared_key,
                assigned_ip=assigned_ip,
            )

        if peer:
            await self._write_peer_config(peer)
            await self._sync_awg()

        return peer

    async def get_peer(self, vpn_subscription_id: int) -> AWGPeer | None:
        async with self.session() as session:
            return await AWGPeer.get_by_subscription(session, vpn_subscription_id)

    async def deactivate_peer(self, vpn_subscription_id: int) -> bool:
        """Deactivate peer and remove its config from the server."""
        if not self.enabled:
            return False

        async with self.session() as session:
            peer = await AWGPeer.get_by_subscription(session, vpn_subscription_id)
            if not peer:
                return False
            await AWGPeer.deactivate(session, vpn_subscription_id)

        self._remove_peer_config(vpn_subscription_id)
        await self._sync_awg()
        return True

    def generate_client_config(self, peer: AWGPeer) -> str:
        """Generate AmneziaWG client config string."""
        server_public_key = self._read_server_public_key()
        return (
            f"[Interface]\n"
            f"PrivateKey = {peer.private_key}\n"
            f"Address = {peer.assigned_ip}/32\n"
            f"DNS = {self.awg.DNS}\n"
            f"Jc = {self.awg.JC}\n"
            f"Jmin = {self.awg.JMIN}\n"
            f"Jmax = {self.awg.JMAX}\n"
            f"S1 = {self.awg.S1}\n"
            f"S2 = {self.awg.S2}\n"
            f"H1 = {self.awg.H1}\n"
            f"H2 = {self.awg.H2}\n"
            f"H3 = {self.awg.H3}\n"
            f"H4 = {self.awg.H4}\n"
            f"\n"
            f"[Peer]\n"
            f"PublicKey = {server_public_key}\n"
            f"PresharedKey = {peer.preshared_key}\n"
            f"Endpoint = {self.awg.SERVER_PUBLIC_IP}:{self.awg.LISTEN_PORT}\n"
            f"AllowedIPs = 0.0.0.0/0\n"
            f"PersistentKeepalive = 25\n"
        )

    def _read_server_public_key(self) -> str:
        """Read the server public key from the config directory."""
        # Try sibling config dir first, then parent/config
        config_dir = self._peers_dir.parent / "awg-config"
        if not config_dir.exists():
            config_dir = self._peers_dir.parent / "config"
        key_path = config_dir / "server_public.key"
        try:
            return key_path.read_text().strip()
        except FileNotFoundError:
            logger.error("Server public key not found at %s", key_path)
            return ""

    async def _write_peer_config(self, peer: AWGPeer) -> None:
        """Write peer config fragment for server-side inclusion."""
        self._peers_dir.mkdir(parents=True, exist_ok=True)
        config_path = self._peers_dir / f"peer_{peer.vpn_subscription_id}.conf"

        content = (
            f"[Peer]\n"
            f"PublicKey = {peer.public_key}\n"
            f"PresharedKey = {peer.preshared_key}\n"
            f"AllowedIPs = {peer.assigned_ip}/32\n"
        )

        config_path.write_text(content)
        logger.debug("Wrote peer config: %s", config_path)

    def _remove_peer_config(self, vpn_subscription_id: int) -> None:
        config_path = self._peers_dir / f"peer_{vpn_subscription_id}.conf"
        try:
            config_path.unlink(missing_ok=True)
            logger.debug("Removed peer config: %s", config_path)
        except OSError as e:
            logger.warning("Failed to remove peer config %s: %s", config_path, e)

    async def _sync_awg(self) -> None:
        """Reload AmneziaWG config inside Docker container."""
        container = self.awg.DOCKER_CONTAINER
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container, "awg-quick", "strip", "/etc/amneziawg/awg0.conf",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode != 0:
                logger.warning("awg-quick strip failed: %s", stderr.decode())

            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container, "awg", "syncconf", "awg0", "/dev/stdin",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=stdout), timeout=10)
            if proc.returncode != 0:
                logger.error("awg syncconf failed: %s", stderr.decode())
            else:
                logger.info("AWG config synced successfully")
        except asyncio.TimeoutError:
            logger.error("AWG sync timed out")
        except Exception as e:
            logger.error("AWG sync error: %s", e)

    async def _generate_keypair(self) -> tuple[str, str]:
        """Generate WireGuard keypair using wg command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wg", "genkey",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            private_key = stdout.decode().strip()

            proc = await asyncio.create_subprocess_exec(
                "wg", "pubkey",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=private_key.encode()), timeout=5)
            public_key = stdout.decode().strip()

            return private_key, public_key
        except Exception as e:
            logger.error("Failed to generate WG keypair: %s", e)
            raise

    async def _generate_preshared_key(self) -> str:
        """Generate WireGuard preshared key."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wg", "genpsk",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return stdout.decode().strip()
        except Exception as e:
            logger.error("Failed to generate WG preshared key: %s", e)
            raise
