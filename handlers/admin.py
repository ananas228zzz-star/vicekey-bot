import re

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import config
import database
from keyboards.main import admin_menu_kb, admin_ref_kb, webapp_kb

router = Router()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


class RefAdmin(StatesGroup):
    waiting_id = State()
    waiting_percent = State()


async def card_text(uid):
    user = await database.get_user(uid)
    name = f" (@{user['username']})" if user and user["username"] else ""
    percent, custom = await database.get_percent(uid)
    s = await database.ref_stats(uid)
    kind = "индивидуальная" if custom else "стандартная"
    return (
        f"👤 Пользователь: <code>{uid}</code>{name}\n"
        f"Комиссия: <b>{percent:g}%</b> ({kind})\n"
        f"Приглашено: {s['invited']}\n"
        f"Приглашённых с покупкой: {s['buyers']}\n"
        f"Успешных покупок: {s['purchases']}\n"
        f"Сумма покупок: {s['sum']:.2f} USDT\n"
        f"Заработано: {s['earned']:.2f} USDT"
    )


async def notify_user(bot: Bot, uid, text):
    try:
        await bot.send_message(uid, text, reply_markup=webapp_kb("ru"))
        return True
    except Exception:
        return False


@router.message(Command("admin"))
async def admin(m: Message, state: FSMContext):
    if m.from_user.id != config.ADMIN_ID:
        return
    await state.clear()
    await m.answer("🛠 Админ-панель", reply_markup=admin_menu_kb())


@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext):
    if m.from_user.id != config.ADMIN_ID:
        return
    await state.clear()
    await m.answer("Отменено")


@router.message(Command("refund"))
async def refund(m: Message, command: CommandObject):
    if m.from_user.id != config.ADMIN_ID:
        return
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await m.answer("Формат: /refund НОМЕР_ЗАКАЗА")
        return
    order_id = int(arg)
    order = await database.get_order(order_id)
    if not order:
        await m.answer("Заказ не найден")
        return
    await database.set_status(order_id, "refunded")
    cancelled = await database.cancel_referral(order_id)
    await m.answer(
        f"Заказ #{order_id} помечен как возвращённый. "
        + ("Реферальное начисление отменено." if cancelled else "Реферального начисления по заказу не было.")
        + "\nДеньги покупателю возвращайте вручную."
    )


@router.callback_query(F.data == "adm:ref")
async def ref_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(RefAdmin.waiting_id)
    await c.message.answer("Отправьте @username или Telegram ID пользователя. Отмена: /cancel")
    await c.answer()


@router.message(RefAdmin.waiting_id)
async def got_id(m: Message, state: FSMContext):
    if m.from_user.id != config.ADMIN_ID:
        return
    text = (m.text or "").strip().replace("https://t.me/", "").replace("t.me/", "")
    if text.isdigit():
        uid = int(text)
    else:
        name = text.lstrip("@")
        if not USERNAME_RE.match(name):
            await m.answer("Отправьте @username или числовой Telegram ID. Отмена: /cancel")
            return
        uid = await database.find_user_by_username(name)
        if uid is None:
            await m.answer(
                f"Пользователь @{name} не найден в базе. Он должен хотя бы один раз запустить бота (/start) или открыть магазин. "
                "Можно отправить его числовой ID. Отмена: /cancel"
            )
            return
    await state.clear()
    await m.answer(await card_text(uid), reply_markup=admin_ref_kb(uid, config.REF_PERCENT))


@router.callback_query(F.data.startswith("adm:set:"))
async def set_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    uid = int(c.data.split(":")[2])
    await state.set_state(RefAdmin.waiting_percent)
    await state.update_data(uid=uid)
    await c.message.answer(f"Введите новый процент от 0 до 100 для пользователя {uid}. Отмена: /cancel")
    await c.answer()


@router.message(RefAdmin.waiting_percent)
async def got_percent(m: Message, state: FSMContext, bot: Bot):
    if m.from_user.id != config.ADMIN_ID:
        return
    raw = (m.text or "").strip().replace(",", ".").replace("%", "")
    try:
        value = float(raw)
    except ValueError:
        value = -1
    if not (0 <= value <= 100):
        await m.answer("Нужно число от 0 до 100. Попробуйте ещё раз или /cancel")
        return
    data = await state.get_data()
    uid = data["uid"]
    await state.clear()
    await database.set_percent(uid, value)
    sent = await notify_user(
        bot,
        uid,
        "🎉 Вам назначена реферальная программа!\n\n"
        f"Ваша комиссия: <b>{value:g}%</b> с каждой покупки пользователей, приглашённых по вашей ссылке.\n\n"
        "Откройте магазин → раздел «Рефералы»: там ваша личная ссылка и статистика.",
    )
    note = "Уведомление пользователю отправлено ✅" if sent else "⚠️ Уведомление не доставлено: пользователь ещё не запускал бота"
    await m.answer("✅ Процент сохранён\n" + note + "\n\n" + await card_text(uid), reply_markup=admin_ref_kb(uid, config.REF_PERCENT))


@router.callback_query(F.data.startswith("adm:reset:"))
async def reset(c: CallbackQuery, bot: Bot):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    uid = int(c.data.split(":")[2])
    await database.reset_percent(uid)
    sent = await notify_user(
        bot,
        uid,
        f"ℹ️ Ваша реферальная комиссия сброшена до стандартных <b>{config.REF_PERCENT:g}%</b>.",
    )
    note = "Уведомление пользователю отправлено ✅" if sent else "⚠️ Уведомление не доставлено"
    await c.message.answer("♻️ Сброшено до стандартного\n" + note + "\n\n" + await card_text(uid), reply_markup=admin_ref_kb(uid, config.REF_PERCENT))
    await c.answer()