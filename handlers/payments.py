from aiogram import Router, F, Bot
from aiogram.types import PreCheckoutQuery, Message, CallbackQuery

import config
import database
from texts import tr
from utils import deliver_key

router = Router()


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def paid(m: Message, bot: Bot):
    payload = m.successful_payment.invoice_payload
    if not payload.startswith("order:"):
        return
    order_id = int(payload.split(":")[1])
    await database.set_status(order_id, "paid")
    await deliver_key(bot, order_id)


@router.callback_query(F.data.startswith("ok:"))
async def confirm(c: CallbackQuery, bot: Bot):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    order_id = int(c.data.split(":")[1])
    order = await database.get_order(order_id)
    if not order or order["status"] == "issued":
        await c.answer("Уже обработан")
        return
    await database.set_status(order_id, "paid")
    key = await deliver_key(bot, order_id)
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(f"Заказ #{order_id}: " + ("ключ выдан ✅" if key else "ключей нет ⚠️"))
    await c.answer()


@router.callback_query(F.data.startswith("no:"))
async def reject(c: CallbackQuery, bot: Bot):
    if c.from_user.id != config.ADMIN_ID:
        await c.answer("Нет доступа", show_alert=True)
        return
    order_id = int(c.data.split(":")[1])
    order = await database.get_order(order_id)
    if not order or order["status"] == "issued":
        await c.answer("Уже обработан")
        return
    await database.set_status(order_id, "rejected")
    await bot.send_message(order["user_id"], tr(order["lang"])["rejected"].format(id=order_id))
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(f"Заказ #{order_id} отклонён")
    await c.answer()