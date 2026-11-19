from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from texts import tr


def webapp_kb(lang="ru"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=tr(lang)["open"], web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    )


def admin_kb(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ok:{order_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no:{order_id}"),
            ]
        ]
    )