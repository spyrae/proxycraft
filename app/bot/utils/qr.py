import asyncio
import io

import segno
from aiogram.types import BufferedInputFile


def _sync_generate_qr(data: str, scale: int = 8) -> bytes:
    """Generate QR code PNG bytes (blocking)."""
    qr = segno.make(data)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


async def generate_qr(data: str, scale: int = 8) -> BufferedInputFile:
    """Generate QR code as aiogram BufferedInputFile (non-blocking)."""
    content = await asyncio.to_thread(_sync_generate_qr, data, scale)
    return BufferedInputFile(file=content, filename="vpn_key_qr.png")
