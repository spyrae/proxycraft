import hashlib
import logging
import uuid
from hmac import compare_digest

import aiohttp
from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import lazy_gettext as __
from aiohttp.web import Application, Request, Response
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import PaymentGateway
from app.bot.utils.constants import TBANK_WEBHOOK, Currency, TransactionStatus
from app.bot.utils.navigation import NavSubscription
from app.config import Config
from app.db.models import Transaction

logger = logging.getLogger(__name__)

TBANK_API_URL = "https://securepay.tinkoff.ru/v2"


class TBank(PaymentGateway):
    name = ""
    currency = Currency.RUB
    callback = NavSubscription.PAY_TBANK

    def __init__(
        self,
        app: Application,
        config: Config,
        session: async_sessionmaker,
        storage: RedisStorage,
        bot: Bot,
        i18n: I18n,
        services: ServicesContainer,
    ) -> None:
        self.name = __("payment:gateway:tbank")
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services

        self.app.router.add_post(TBANK_WEBHOOK, self.webhook_handler)
        logger.info("T-Bank payment gateway initialized.")

    def _generate_token(self, params: dict) -> str:
        """Generate Token for T-Bank API request signing.

        Algorithm per T-Bank docs:
        1. Add Password to params dict
        2. Exclude Token, nested objects/arrays, None and empty values
        3. Sort by key alphabetically
        4. Concatenate all values as strings (booleans lowercase)
        5. SHA-256 hash the result
        """
        token_params = {**params}
        token_params["Password"] = self.config.tbank.PASSWORD

        filtered = {}
        for k, v in token_params.items():
            if k == "Token" or isinstance(v, (dict, list)) or v is None or v == "":
                continue
            if isinstance(v, bool):
                filtered[k] = str(v).lower()
            else:
                filtered[k] = v

        sorted_keys = sorted(filtered.keys())
        values_string = "".join(str(filtered[key]) for key in sorted_keys)
        return hashlib.sha256(values_string.encode()).hexdigest()

    async def _api_request(self, method: str, data: dict) -> dict:
        """Make API request to T-Bank API v2."""
        data["TerminalKey"] = self.config.tbank.TERMINAL_KEY
        data["Token"] = self._generate_token(data)

        url = f"{TBANK_API_URL}/{method}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()
                if not result.get("Success"):
                    error_code = result.get("ErrorCode", "unknown")
                    error_msg = result.get("Message", "Unknown error")
                    details = result.get("Details", "")
                    raise Exception(
                        f"T-Bank API error: {error_code} - {error_msg}. "
                        f"Details: {details}. Method: {method}"
                    )
                return result

    async def create_payment(self, data: SubscriptionData) -> str:
        bot_username = (await self.bot.get_me()).username
        redirect_url = f"https://t.me/{bot_username}"
        order_id = str(uuid.uuid4())
        price_kopecks = int(round(data.price * 100))

        init_data = {
            "Amount": price_kopecks,
            "OrderId": order_id,
            "PayType": "O",
            "NotificationURL": self.config.bot.DOMAIN + TBANK_WEBHOOK,
            "SuccessURL": redirect_url,
            "FailURL": redirect_url,
        }

        result = await self._api_request("Init", init_data)
        payment_id = result["PaymentId"]
        pay_url = result["PaymentURL"]

        async with self.session() as session:
            await Transaction.create(
                session=session,
                tg_id=data.user_id,
                subscription=data.pack(),
                payment_id=str(payment_id),
                status=TransactionStatus.PENDING,
            )

        logger.info(f"T-Bank payment link created for user {data.user_id}: {pay_url}")
        return pay_url

    async def handle_payment_succeeded(self, payment_id: str) -> None:
        await self._on_payment_succeeded(payment_id)

    async def handle_payment_canceled(self, payment_id: str) -> None:
        await self._on_payment_canceled(payment_id)

    def _verify_webhook(self, data: dict) -> bool:
        """Verify incoming webhook Token signature."""
        received_token = data.get("Token")
        if not received_token:
            logger.warning("T-Bank webhook: missing Token")
            return False

        # Build params without Token field for verification
        params = {k: v for k, v in data.items() if k != "Token"}
        expected_token = self._generate_token(params)

        if not compare_digest(received_token, expected_token):
            logger.warning("T-Bank webhook: invalid Token signature")
            return False

        return True

    async def webhook_handler(self, request: Request) -> Response:
        logger.debug("Received T-Bank webhook request")
        try:
            event_json = await request.json()

            if not self._verify_webhook(event_json):
                return Response(status=403)

            payment_id = str(event_json.get("PaymentId", ""))
            status = event_json.get("Status")

            match status:
                case "CONFIRMED":
                    await self.handle_payment_succeeded(payment_id)
                    return Response(text="OK", status=200)

                case "REJECTED" | "CANCELED" | "DEADLINE_EXPIRED" | "AUTH_FAIL":
                    await self.handle_payment_canceled(payment_id)
                    return Response(text="OK", status=200)

                case _:
                    # Intermediate statuses (AUTHORIZED, etc.) — acknowledge
                    logger.debug(f"T-Bank webhook: intermediate status {status}")
                    return Response(text="OK", status=200)

        except Exception as exception:
            logger.exception(f"Error processing T-Bank webhook: {exception}")
            return Response(status=400)


class TBankSBP(TBank):
    """T-Bank SBP (Sistem Bystrykh Platezhey) payment gateway.

    Inherits from TBank, overrides create_payment to use Init + GetQr flow.
    Shares the same webhook handler (payments arrive at /tbank for both).
    """

    callback = NavSubscription.PAY_TBANK_SBP

    def __init__(
        self,
        app: Application,
        config: Config,
        session: async_sessionmaker,
        storage: RedisStorage,
        bot: Bot,
        i18n: I18n,
        services: ServicesContainer,
    ) -> None:
        self.name = __("payment:gateway:tbank_sbp")
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services

        # Don't register webhook again — TBank parent already did it
        logger.info("T-Bank SBP payment gateway initialized.")

    async def create_payment(self, data: SubscriptionData) -> str:
        order_id = str(uuid.uuid4())
        price_kopecks = int(round(data.price * 100))

        init_data = {
            "Amount": price_kopecks,
            "OrderId": order_id,
            "PayType": "O",
            "NotificationURL": self.config.bot.DOMAIN + TBANK_WEBHOOK,
        }

        result = await self._api_request("Init", init_data)
        payment_id = result["PaymentId"]

        # Get SBP QR code
        qr_data = {
            "PaymentId": payment_id,
        }
        qr_result = await self._api_request("GetQr", qr_data)
        pay_url = qr_result["Data"]

        async with self.session() as session:
            await Transaction.create(
                session=session,
                tg_id=data.user_id,
                subscription=data.pack(),
                payment_id=str(payment_id),
                status=TransactionStatus.PENDING,
            )

        logger.info(f"T-Bank SBP payment created for user {data.user_id}")
        return pay_url
