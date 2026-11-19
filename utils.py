from aiogram import Bot
from aiogram.utils.web_app import safe_parse_webapp_init_data

import config
import database
from texts import tr


def parse_user(init_data):
    data = safe_parse_webapp_init_data(token=config.BOT_TOKEN, init_data=init_data)
    return data.user


async def notify_admin(bot: Bot, text, kb=None):
    if not config.ADMIN_ID:
        return
    try:
        await bot.send_message(config.ADMIN_ID, text, reply_markup=kb)
    except Exception:
        pass


async def deliver_key(bot: Bot, order_id):
    order = await database.get_order(order_id)
    if not order:
        return None
    t = tr(order["lang"])
    key = await database.issue_key(order_id)
    if not key:
        await database.set_status(order_id, "paid_no_stock")
        await bot.send_message(order["user_id"], t["no_stock"])
        await notify_admin(
            bot,
            f"⚠️ Заказ #{order_id} оплачен, но ключей нет: {order['edition']} {order['platform']} {order['region']}. Добавьте ключи через /addkeys и выдайте вручную.",
        )
        return None
    name = "GTA VI: " + config.EDITION_NAMES[order["edition"]]
    await bot.send_message(
        order["user_id"],
        t["key_ok"].format(name=name, platform=order["platform"].upper(), region=order["region"], key=key),
    )
    return key