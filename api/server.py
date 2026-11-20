from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from aiogram import Bot
from aiogram.types import LabeledPrice

import config
import database
import utils
from keyboards.main import admin_kb

INDEX = config.BASE_DIR / "webapp" / "index.html"


class OrderIn(BaseModel):
    edition: str
    platform: str
    region: str
    method: str
    lang: str = "ru"


def create_app(bot: Bot):
    app = FastAPI()

    async def auth(x_init_data: str = Header(default="")):
        try:
            user = utils.parse_user(x_init_data)
        except Exception:
            raise HTTPException(status_code=401, detail="unauthorized")
        if not user:
            raise HTTPException(status_code=401, detail="unauthorized")
        await database.register_user(user.id, None, user.username)
        await database.touch_activity(user.id)
        return user.id

    @app.get("/")
    async def index():
        return FileResponse(INDEX)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/bootstrap")
    async def bootstrap(uid: int = Depends(auth)):
        return {
            "discount": config.DISCOUNT,
            "editions": config.EDITIONS,
            "regions": config.REGIONS,
            "stock": await database.stock_map(),
            "keys": await database.user_orders(uid),
            "support": config.SUPPORT_USERNAME,
            "ton": config.TON_ADDRESS,
            "trc20": config.TRC20_ADDRESS,
            "binance": config.BINANCE_PAY_ID,
        }

    @app.get("/api/referral")
    async def referral(uid: int = Depends(auth)):
        me = await bot.me()
        percent, custom = await database.get_percent(uid)
        return {
            "link": f"https://t.me/{me.username}?start=ref_{uid}",
            "percent": percent,
            "custom": custom,
            "stats": await database.ref_stats(uid),
        }

    @app.post("/api/order")
    async def order(data: OrderIn, uid: int = Depends(auth)):
        if (
            data.edition not in config.EDITIONS
            or data.platform not in config.PLATFORMS
            or data.region not in config.REGIONS
            or data.method not in config.METHODS
        ):
            raise HTTPException(status_code=400, detail="bad request")
        if await database.stock_count(data.edition, data.platform, data.region) < 1:
            raise HTTPException(status_code=409, detail="out of stock")
        lang = "en" if data.lang == "en" else "ru"
        usdt, stars = config.calc_price(data.edition, data.region)
        order_id = await database.create_order(uid, data.edition, data.platform, data.region, data.method, usdt, stars, lang)
        result = {"id": order_id, "usdt": usdt, "stars": stars, "invoice_url": None}
        if data.method == "stars":
            title = "GTA VI " + config.EDITION_NAMES[data.edition]
            result["invoice_url"] = await bot.create_invoice_link(
                title=title,
                description=f"{data.platform.upper()} / {data.region}",
                payload=f"order:{order_id}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=title, amount=stars)],
            )
        return result

    @app.post("/api/order/{order_id}/paid")
    async def mark_paid(order_id: int, uid: int = Depends(auth)):
        o = await database.get_order(order_id)
        if not o or o["user_id"] != uid or o["method"] == "stars":
            raise HTTPException(status_code=404, detail="not found")
        if o["status"] == "new":
            await database.set_status(order_id, "pending_review")
            await utils.notify_admin(
                bot,
                f"💰 Заказ #{order_id}\n{o['edition']} {o['platform']} {o['region']}\nМетод: {o['method']}\nСумма: {o['usdt']} USDT\nПокупатель: <a href=\"tg://user?id={uid}\">{uid}</a>\n\nПроверьте поступление и подтвердите.",
                admin_kb(order_id),
            )
        return {"status": "pending_review"}

    @app.get("/api/order/{order_id}")
    async def get_order(order_id: int, uid: int = Depends(auth)):
        o = await database.get_order(order_id)
        if not o or o["user_id"] != uid:
            raise HTTPException(status_code=404, detail="not found")
        return {"status": o["status"], "key": o["key"]}

    return app