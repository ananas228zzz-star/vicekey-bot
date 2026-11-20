import logging

from aiogram import BaseMiddleware

import database

log = logging.getLogger("activity")


class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and not user.is_bot and getattr(event, "event_type", "") != "my_chat_member":
            try:
                await database.touch_activity(user.id, from_bot=True)
            except Exception:
                log.exception("touch_activity failed")
        return await handler(event, data)