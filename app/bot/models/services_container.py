from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import (
        NotificationService,
        ServerPoolService,
        VPNService,
        ReferralService,
        SubscriptionService,
        PaymentStatsService,
        InviteStatsService,
        MTProtoService,
        WhatsAppService,
    )
    from app.bot.services.amneziawg import AmneziaWGService
    from app.bot.services.bundle import BundleService
    from app.bot.services.product_catalog import ProductCatalog

from dataclasses import dataclass


@dataclass
class ServicesContainer:
    server_pool: ServerPoolService
    vpn: VPNService
    notification: NotificationService
    referral: ReferralService
    subscription: SubscriptionService
    payment_stats: PaymentStatsService
    invite_stats: InviteStatsService
    mtproto: MTProtoService
    whatsapp: WhatsAppService
    amneziawg: AmneziaWGService
    product_catalog: ProductCatalog
    bundle: BundleService
