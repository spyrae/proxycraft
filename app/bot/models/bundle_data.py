from aiogram.filters.callback_data import CallbackData

from app.bot.utils.navigation import NavBundle


class BundleData(CallbackData, prefix="bundle"):
    state: NavBundle
    slug: str = ""
    user_id: int = 0
    duration: int = 0
    price: int = 0
    is_extend: bool = False
