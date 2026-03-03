import logging

from aiogram import Bot
from aiohttp.web import Application
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.api.middleware import cors_middleware, tma_auth_middleware
from app.bot.api.routes import register_routes
from app.bot.models import ServicesContainer
from app.bot.payment_gateways import GatewayFactory
from app.config import Config

logger = logging.getLogger(__name__)


def register_api_routes(
    app: Application,
    config: Config,
    session: async_sessionmaker,
    bot: Bot,
    services: ServicesContainer,
    gateway_factory: GatewayFactory,
) -> None:
    """Register Mini App API routes on the aiohttp application."""
    app["config"] = config
    app["session"] = session
    app["bot"] = bot
    app["services"] = services
    app["gateway_factory"] = gateway_factory

    app.middlewares.append(cors_middleware)
    app.middlewares.append(tma_auth_middleware)

    register_routes(app)

    logger.info("Mini App API routes registered.")
