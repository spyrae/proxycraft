from aiogram.filters.callback_data import CallbackData

from app.bot.utils.navigation import NavWhatsApp


class WhatsAppData(CallbackData, prefix="whatsapp"):
    state: NavWhatsApp
    user_id: int = 0
    duration: int = 0
    price: int = 0
    is_extend: bool = False
