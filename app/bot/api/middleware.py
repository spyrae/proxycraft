import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs, unquote

from aiohttp import web
from aiohttp.web import Request, Response, middleware

from app.db.models import User

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

ALLOWED_ORIGINS = [
    "https://app.vpncraft.tech",
    "https://vpncraft-webapp.pages.dev",
    "http://localhost:5173",
    "http://localhost:4173",
]

MAX_AUTH_AGE_SECONDS = 3600  # 1 hour


def _is_allowed_origin(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    # Allow Cloudflare Pages preview deployments
    if origin.endswith(".vpncraft-webapp.pages.dev") and origin.startswith("https://"):
        return True
    return False


def _cors_headers(origin: str | None) -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Max-Age": "86400",
    }
    if origin and _is_allowed_origin(origin):
        headers["Access-Control-Allow-Origin"] = origin
    return headers


@middleware
async def cors_middleware(request: Request, handler) -> Response:
    origin = request.headers.get("Origin")
    cors = _cors_headers(origin)

    if request.method == "OPTIONS" and request.path.startswith(API_PREFIX):
        return Response(status=204, headers=cors)

    response = await handler(request)

    for key, value in cors.items():
        response.headers[key] = value

    return response


def _validate_init_data(init_data_raw: str, bot_token: str) -> dict | None:
    """Validate Telegram Mini App initData using HMAC-SHA256.

    Returns parsed user data dict on success, None on failure.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = parse_qs(init_data_raw)
    except Exception:
        return None

    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        return None

    # Build data-check-string: sorted key=value pairs excluding hash
    data_pairs = []
    for key, values in parsed.items():
        if key == "hash":
            continue
        data_pairs.append(f"{key}={unquote(values[0])}")
    data_pairs.sort()
    data_check_string = "\n".join(data_pairs)

    # HMAC-SHA256 verification
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # Check auth_date freshness
    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        try:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > MAX_AUTH_AGE_SECONDS:
                logger.warning("initData auth_date too old")
                return None
        except ValueError:
            return None

    # Parse user JSON
    user_json = parsed.get("user", [None])[0]
    if not user_json:
        return None

    try:
        return json.loads(unquote(user_json))
    except json.JSONDecodeError:
        return None


@middleware
async def tma_auth_middleware(request: Request, handler) -> Response:
    """Authenticate requests to /api/v1/* using Telegram Mini App initData."""
    if not request.path.startswith(API_PREFIX):
        return await handler(request)

    if request.method == "OPTIONS":
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        return web.json_response({"error": "Missing or invalid Authorization header"}, status=401)

    init_data_raw = auth_header[4:]
    bot_token = request.app["config"].bot.TOKEN

    tg_user = _validate_init_data(init_data_raw, bot_token)
    if not tg_user:
        return web.json_response({"error": "Invalid initData"}, status=401)

    tg_id = tg_user.get("id")
    if not tg_id:
        return web.json_response({"error": "No user id in initData"}, status=401)

    # Load user from DB
    session_factory = request.app["session"]
    async with session_factory() as session:
        user = await User.get(session=session, tg_id=tg_id)

    if not user:
        return web.json_response({"error": "User not found"}, status=404)

    request["user"] = user
    request["tg_id"] = tg_id
    request["tg_user"] = tg_user

    return await handler(request)
