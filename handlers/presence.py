from aiogram import Router
from aiogram.types import ChatMemberUpdated

import database

router = Router()


@router.my_chat_member()
async def on_member_update(e: ChatMemberUpdated):
    if e.chat.type != "private":
        return
    status = e.new_chat_member.status
    if status in ("kicked", "left"):
        await database.set_blocked(e.chat.id, True)
    elif status == "member":
        await database.set_blocked(e.chat.id, False)