from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import config
import database
from keyboards.main import admin_menu_kb, admin_ref_kb

router = Router()


class RefAdmin(StatesGroup):
    waiting_id = State()
    waiting_percent = State()


async def card_text(uid):
    percent, custom = await database.get_percent(uid)
    s = await database.ref_stats(uid)
    kind = "индивидуальная" if custom else "стандартная"
    return (
        f"👤 Пользователь: <code>{uid}</code>\n"
        f"Комиссия: <b>{percent:g}%</b> ({kind})\n"
        f"Приглашено: {s['invited']}\n"
        f"Приглашённых с покупкой: {s['buyers']}\n"
        f"Успешных покупок: {s['purchases']}\n"
        f"Сумма покупок: {s['sum']:.2f} USDT\n"
        f"Заработано: {s['earned']:.2f} USDT"
    )


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
    await c.message.answer("Отправьте Telegram ID пользователя (только цифры). Отмена: /cancel")
    await c.answer()


@router.message(RefAdmin.waiting_id)
async def got_id(m: Message, state: FSMContext):
    if m.from_user.id != config.ADMIN_ID:
        return
    text = (m.text or "").strip()
    if not text.isdigit():
        await m.answer("Нужен числовой Telegram ID. Попробуйте ещё раз или /cancel")
        return
    uid = int(text)
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
async def got_percent(m: Message, state: FSMContext):
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
    await m.answer("✅ Процент сохранён\n\n" + await card_text(uid), reply_markup=admin_ref_kb(uid, config.REF_PERCENT))


@router.callback_query(F.data.startswith("adm:reset:"))
async def reset(c: CallbackQuery):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    uid = int(c.data.split(":")[2])
    await database.reset_percent(uid)
    await c.message.answer("♻️ Сброшено до стандартного\n\n" + await card_text(uid), reply_markup=admin_ref_kb(uid, config.REF_PERCENT))
    await c.answer()