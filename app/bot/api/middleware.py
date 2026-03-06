import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs, unquote

from aiohttp import web
from aiohttp.web import Request, Response, middleware

from app.db.models import User
from app.bot.filters.is_admin import IsAdmin

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

ALLOWED_ORIGINS = [
    "https://app.proxycraft.tech",
    "https://app.proxycraft.tech",
    "https://proxycraft-webapp.pages.dev",
    "https://admin.proxycraft.tech",
    "https://admin.proxycraft.tech",
    "http://localhost:5173",
    "http://localhost:4173",
]

MAX_AUTH_AGE_SECONDS = 3600  # 1 hour
ADMIN_TOKEN_TTL = 86400  # 24 hours
TELEGRAM_LOGIN_MAX_AGE = 86400  # 24 hours

# Paths that don't require TMA auth
AUTH_EXEMPT_PATHS = {
    "/api/v1/admin/auth",
}


def _is_allowed_origin(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    # Allow Cloudflare Pages preview deployments
    if origin.endswith(".proxycraft-webapp.pages.dev") and origin.startswith("https://"):
        return True
    if origin.endswith(".proxycraft-admin.pages.dev") and origin.startswith("https://"):
        return True
    if origin.endswith(".proxycraft-landing.pages.dev") and origin.startswith("https://"):
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


# ---------- Telegram Login Widget auth ----------


def _validate_telegram_login(data: dict, bot_token: str) -> bool:
    """Validate Telegram Login Widget data using SHA256-based HMAC.

    Unlike TMA (which uses HMAC of "WebAppData"), Login Widget uses
    SHA256(bot_token) as the secret key directly.
    See: https://core.telegram.org/widgets/login#checking-authorization
    """
    received_hash = data.get("hash")
    if not received_hash:
        return False

    # Check auth_date freshness
    auth_date = data.get("auth_date")
    if not auth_date:
        return False
    try:
        if time.time() - int(auth_date) > TELEGRAM_LOGIN_MAX_AGE:
            return False
    except (ValueError, TypeError):
        return False

    # Build data-check-string: sorted key=value pairs excluding hash
    check_pairs = sorted(
        f"{k}={v}" for k, v in data.items() if k != "hash"
    )
    data_check_string = "\n".join(check_pairs)

    # Secret key = SHA256(bot_token) — NOT HMAC like TMA!
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)


def _create_admin_token(tg_id: int, bot_token: str) -> str:
    """Create a signed admin JWT-like token.

    Format: base64url(json_payload).hmac_signature
    Payload: {"tg_id": int, "exp": unix_timestamp}
    """
    payload = json.dumps({"tg_id": tg_id, "exp": int(time.time()) + ADMIN_TOKEN_TTL})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(bot_token.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def _validate_admin_token(token: str, bot_token: str) -> int | None:
    """Validate admin token and return tg_id, or None if invalid/expired."""
    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, received_sig = parts

    # Verify HMAC signature
    expected_sig = hmac.new(
        bot_token.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        return None

    # Decode payload
    try:
        # Add padding back
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (json.JSONDecodeError, Exception):
        return None

    # Check expiration
    exp = payload.get("exp", 0)
    if time.time() > exp:
        return None

    return payload.get("tg_id")


@middleware
async def tma_auth_middleware(request: Request, handler) -> Response:
    """Authenticate requests to /api/v1/* using Telegram Mini App initData or Bearer token."""
    if not request.path.startswith(API_PREFIX):
        return await handler(request)

    if request.method == "OPTIONS":
        return await handler(request)

    # Skip auth for exempt paths
    if request.path in AUTH_EXEMPT_PATHS:
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    bot_token = request.app["config"].bot.TOKEN
    session_factory = request.app["session"]

    # Bearer token auth (admin panel)
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        tg_id = _validate_admin_token(token, bot_token)
        if not tg_id:
            return web.json_response({"error": "Invalid or expired token"}, status=401)

        async with session_factory() as session:
            user = await User.get(session=session, tg_id=tg_id)

        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        request["user"] = user
        request["tg_id"] = tg_id
        request["tg_user"] = {"id": tg_id}

        return await handler(request)

    # TMA initData auth (Telegram Mini App)
    if auth_header.startswith("tma "):
        init_data_raw = auth_header[4:]

        tg_user = _validate_init_data(init_data_raw, bot_token)
        if not tg_user:
            return web.json_response({"error": "Invalid initData"}, status=401)

        tg_id = tg_user.get("id")
        if not tg_id:
            return web.json_response({"error": "No user id in initData"}, status=401)

        async with session_factory() as session:
            user = await User.get(session=session, tg_id=tg_id)

        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        request["user"] = user
        request["tg_id"] = tg_id
        request["tg_user"] = tg_user

        return await handler(request)

    return web.json_response({"error": "Missing or invalid Authorization header"}, status=401)


async def require_admin(request: Request) -> None:
    """Check that the authenticated user is an admin. Raise 403 if not."""
    tg_id = request["tg_id"]
    if not await IsAdmin()(user_id=tg_id):
        raise web.HTTPForbidden(
            text='{"error":"Admin access required"}',
            content_type="application/json",
        )
