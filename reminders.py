import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

import database
from keyboards.main import webapp_kb

log = logging.getLogger("reminders")

MSK = timezone(timedelta(hours=3))
CHECK_INTERVAL = 12 * 60
SEND_PAUSE = 0.1
MIN_GAP = 6 * 3600
NIGHT_START = 0
NIGHT_END = 9
BATCH_LIMIT = 1000

DELAYS = {1: 3 * 3600, 2: 24 * 3600, 3: 72 * 3600}

TEXTS = {
    1: "<b>Ты всё ещё не забрал свой ключ GTA 6?</b> 🌴\n\nВайс-Сити никого не ждёт — загляни обратно в магазин, пока всё на месте. Быстрая выдача и оплата в пару кликов.",
    2: "<b>Хей, ты оставил кое-что в ViceKey 👀</b>\n\nЗаходил глянуть ключи на GTA 6 и пропал. Возвращайся — оформить заказ можно за минуту через крипту, Binance Pay или Stars.",
    3: "<b>Последний пинг от ViceKey 🌆</b>\n\nЕсли всё ещё присматриваешь ключ на GTA 6 — магазин открыт, всё работает в автоматическом режиме. Залетай, когда будешь готов.",
}


def is_night(now=None):
    hour = (now or datetime.now(MSK)).hour
    return NIGHT_START <= hour < NIGHT_END


async def send_one(bot: Bot, user_id, stage):
    for attempt in (1, 2):
        try:
            await bot.send_message(user_id, TEXTS[stage], reply_markup=webapp_kb("ru"))
            return "sent"
        except TelegramRetryAfter as e:
            if attempt == 2:
                return "fail"
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            return "blocked"
        except TelegramBadRequest as e:
            text = str(e).lower()
            if "chat not found" in text or "user is deactivated" in text:
                return "blocked"
            log.warning("bad request for %s: %s", user_id, e)
            return "fail"
        except TelegramAPIError as e:
            log.warning("send failed for %s: %s", user_id, e)
            return "fail"
    return "fail"


async def run_cycle(bot: Bot):
    if is_night():
        return 0
    due = await database.due_reminders(int(time.time()), DELAYS, MIN_GAP, BATCH_LIMIT)
    sent = 0
    for user_id, stage, last_activity in due:
        if is_night():
            break
        target = stage + 1
        result = await send_one(bot, user_id, target)
        if result == "sent":
            await database.set_stage(user_id, target, int(time.time()), last_activity)
            sent += 1
        elif result == "blocked":
            await database.set_blocked(user_id, True)
        await asyncio.sleep(SEND_PAUSE)
    return sent


async def reminder_loop(bot: Bot):
    await asyncio.sleep(30)
    while True:
        try:
            n = await run_cycle(bot)
            if n:
                log.info("reminders sent: %s", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("reminder cycle failed")
        await asyncio.sleep(CHECK_INTERVAL)