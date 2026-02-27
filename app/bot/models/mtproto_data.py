from aiogram.filters.callback_data import CallbackData

from app.bot.utils.navigation import NavMTProto


class MTProtoData(CallbackData, prefix="mtproto"):
    state: NavMTProto
    user_id: int = 0
    duration: int = 0
    price: int = 0
    is_extend: bool = False
