from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from texts import tr


def webapp_kb(lang="ru"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=tr(lang)["open"], web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    )


def start_kb(lang="ru"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(lang)["open"], web_app=WebAppInfo(url=config.WEBAPP_URL))],
            [InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref:menu")],
        ]
    )


def ref_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Моя реферальная ссылка", callback_data="ref:link")],
            [InlineKeyboardButton(text="📊 Моя реферальная статистика", callback_data="ref:stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref:back")],
        ]
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


def admin_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👥 Рефералы", callback_data="adm:ref")]]
    )


def admin_ref_kb(uid, default_percent):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить процент", callback_data=f"adm:set:{uid}")],
            [InlineKeyboardButton(text=f"♻️ Сбросить до {default_percent:g}%", callback_data=f"adm:reset:{uid}")],
        ]
    )