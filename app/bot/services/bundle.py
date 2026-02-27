from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services.mtproto import MTProtoService
    from app.bot.services.product_catalog import ProductCatalog
    from app.bot.services.vpn import VPNService
    from app.bot.services.whatsapp import WhatsAppService
    from app.db.models import User

logger = logging.getLogger(__name__)


class BundleService:
    def __init__(
        self,
        catalog: ProductCatalog,
        mtproto: MTProtoService,
        whatsapp: WhatsAppService,
        vpn: VPNService,
    ) -> None:
        self.catalog = catalog
        self.mtproto = mtproto
        self.whatsapp = whatsapp
        self.vpn = vpn
        logger.info("BundleService initialized.")

    async def activate(
        self,
        slug: str,
        user_tg_id: int,
        user: User,
        duration: int,
        is_trial: bool = False,
    ) -> dict[str, Any]:
        """Activate all components of a bundle. Returns results per component."""
        product = self.catalog.get_product(slug)
        if not product or not product.is_bundle:
            raise ValueError(f"Not a valid bundle: {slug}")

        results: dict[str, Any] = {}

        for component in product.includes:
            try:
                if component == "mtproto":
                    secret = await self.mtproto.activate(user_tg_id, duration, is_trial=is_trial)
                    results["mtproto"] = {"success": secret is not None, "secret": secret}
                elif component == "socks5":
                    port = await self.whatsapp.activate(user_tg_id, duration, is_trial=is_trial)
                    results["whatsapp"] = {"success": port is not None, "port": port}
                elif component == "vpn":
                    success = await self.vpn.create_subscription(
                        user=user, devices=1, duration=duration
                    )
                    results["vpn"] = {"success": success}
                else:
                    logger.warning(f"Unknown bundle component: {component}")
                    results[component] = {"success": False, "error": "unknown component"}
            except Exception as e:
                logger.error(f"Error activating {component} for user {user_tg_id}: {e}")
                results[component] = {"success": False, "error": str(e)}

        logger.info(f"Bundle '{slug}' activated for user {user_tg_id}: {results}")
        return results

    async def extend(
        self,
        slug: str,
        user_tg_id: int,
        user: User,
        duration: int,
    ) -> dict[str, Any]:
        """Extend all components of a bundle."""
        product = self.catalog.get_product(slug)
        if not product or not product.is_bundle:
            raise ValueError(f"Not a valid bundle: {slug}")

        results: dict[str, Any] = {}

        for component in product.includes:
            try:
                if component == "mtproto":
                    success = await self.mtproto.extend(user_tg_id, duration)
                    results["mtproto"] = {"success": success}
                elif component == "socks5":
                    success = await self.whatsapp.extend(user_tg_id, duration)
                    results["whatsapp"] = {"success": success}
                elif component == "vpn":
                    success = await self.vpn.extend_subscription(
                        user=user, devices=1, duration=duration
                    )
                    results["vpn"] = {"success": success}
                else:
                    logger.warning(f"Unknown bundle component: {component}")
                    results[component] = {"success": False, "error": "unknown component"}
            except Exception as e:
                logger.error(f"Error extending {component} for user {user_tg_id}: {e}")
                results[component] = {"success": False, "error": str(e)}

        logger.info(f"Bundle '{slug}' extended for user {user_tg_id}: {results}")
        return results
