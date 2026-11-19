from aiogram import Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message

import config
import database
from keyboards.main import start_kb
from texts import tr

router = Router()


@router.message(CommandStart())
async def start(m: Message, command: CommandObject):
    ref = None
    arg = command.args or ""
    if arg.startswith("ref_") and arg[4:].isdigit():
        ref = int(arg[4:])
    await database.register_user(m.from_user.id, ref)
    lang = "en" if (m.from_user.language_code or "ru") != "ru" else "ru"
    await m.answer(tr(lang)["start"], reply_markup=start_kb(lang))


@router.message(Command("addkeys"))
async def addkeys(m: Message):
    if m.from_user.id != config.ADMIN_ID:
        return
    lines = (m.text or "").split("\n")
    head = lines[0].split()
    ok = (
        len(head) == 4
        and head[1] in config.EDITIONS
        and head[2] in config.PLATFORMS
        and head[3] in config.REGIONS
    )
    if not ok:
        await m.answer("Формат: /addkeys std ps5 GL\nНиже по одному ключу в каждой строке.\nstd/ult, ps5/xbox, GL/TR/UA/US/EU")
        return
    keys = [x.strip() for x in lines[1:] if x.strip()]
    n = await database.add_keys(head[1], head[2], head[3], keys)
    await m.answer(f"Добавлено ключей: {n}")


@router.message(Command("stock"))
async def stock(m: Message):
    if m.from_user.id != config.ADMIN_ID:
        return
    data = await database.stock_map()
    if not data:
        await m.answer("Склад пуст")
        return
    out = []
    for platform, eds in data.items():
        for ed, regs in eds.items():
            out.append(f"{platform} {ed}: " + ", ".join(f"{r}={n}" for r, n in regs.items()))
    await m.answer("\n".join(out))