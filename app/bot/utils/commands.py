import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonWebApp, WebAppInfo

from .constants import WEBAPP_URL
from .navigation import NavMain

logger = logging.getLogger(__name__)


def _menu_button_text(language_code: str | None) -> str:
    if language_code and language_code.startswith("ru"):
        return "Открыть приложение"
    return "Open App"


async def setup(bot: Bot) -> None:
    commands = [
        BotCommand(command=NavMain.START, description="Открыть главное меню"),
        BotCommand(command="ref", description="Реферальная программа"),
    ]

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllPrivateChats(),
    )

    # Set default menu button (global fallback for all chats)
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open App",
            web_app=WebAppInfo(url=WEBAPP_URL),
        ),
    )
    logger.info("Bot commands and menu button configured successfully.")


async def set_user_menu_button(bot: Bot, chat_id: int, language_code: str | None) -> None:
    await bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(
            text=_menu_button_text(language_code),
            web_app=WebAppInfo(url=WEBAPP_URL),
        ),
    )


async def delete(bot: Bot) -> None:
    await bot.delete_my_commands(
        scope=BotCommandScopeAllPrivateChats(),
    )
    logger.info("Bot commands removed successfully.")
