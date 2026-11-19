from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

import database
from keyboards.main import ref_menu_kb, start_kb
from texts import tr

router = Router()

MENU_TEXT = (
    "👥 <b>Реферальная система</b>\n\n"
    "Приглашайте друзей по своей ссылке и получайте процент с каждой их покупки.\n"
    "Выберите действие:"
)


async def safe_edit(c: CallbackQuery, text, kb):
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "ref:menu")
async def menu(c: CallbackQuery):
    await safe_edit(c, MENU_TEXT, ref_menu_kb())
    await c.answer()


@router.callback_query(F.data == "ref:link")
async def link(c: CallbackQuery, bot: Bot):
    uid = c.from_user.id
    await database.register_user(uid)
    percent, _ = await database.get_percent(uid)
    me = await bot.me()
    url = f"https://t.me/{me.username}?start=ref_{uid}"
    text = (
        "🔗 <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{url}</code>\n\n"
        f"Ваша комиссия: <b>{percent:g}%</b> с каждой покупки приглашённых.\n"
        "Покупатель платит обычную цену — комиссия это ваше вознаграждение."
    )
    await safe_edit(c, text, ref_menu_kb())
    await c.answer()


@router.callback_query(F.data == "ref:stats")
async def stats(c: CallbackQuery, bot: Bot):
    uid = c.from_user.id
    await database.register_user(uid)
    percent, _ = await database.get_percent(uid)
    s = await database.ref_stats(uid)
    me = await bot.me()
    url = f"https://t.me/{me.username}?start=ref_{uid}"
    text = (
        "📊 <b>Моя реферальная статистика</b>\n\n"
        f"Ссылка: <code>{url}</code>\n"
        f"Комиссия: <b>{percent:g}%</b>\n"
        f"Приглашено пользователей: {s['invited']}\n"
        f"Из них совершили покупку: {s['buyers']}\n"
        f"Успешных реферальных покупок: {s['purchases']}\n"
        f"Сумма покупок приглашённых: {s['sum']:.2f} USDT\n"
        f"Заработано: <b>{s['earned']:.2f} USDT</b>"
    )
    await safe_edit(c, text, ref_menu_kb())
    await c.answer()


@router.callback_query(F.data == "ref:back")
async def back(c: CallbackQuery):
    lang = "en" if (c.from_user.language_code or "ru") != "ru" else "ru"
    await safe_edit(c, tr(lang)["start"], start_kb(lang))
    await c.answer()