import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").lstrip("@")
TON_ADDRESS = os.getenv("TON_ADDRESS", "")
TRC20_ADDRESS = os.getenv("TRC20_ADDRESS", "")
BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", "")
PORT = int(os.getenv("PORT", "8000"))
DISCOUNT = float(os.getenv("PRICE_MULTIPLIER", "0.8"))

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "shop.db"

EDITIONS = {
    "std": {"usdt": 69.99, "stars": 5400},
    "ult": {"usdt": 109.99, "stars": 8500},
}
EDITION_NAMES = {"std": "Standard Edition", "ult": "Ultimate Edition"}
REGIONS = {"GL": 1.0, "TR": 0.72, "UA": 0.78, "US": 1.08, "EU": 1.04}
PLATFORMS = ("ps5", "xbox")
METHODS = ("stars", "binance", "ton", "trc20")


def calc_price(edition, region):
    base = EDITIONS[edition]
    k = REGIONS[region]
    usdt = round(base["usdt"] * k * DISCOUNT, 2)
    stars = max(1, round(base["stars"] * k * DISCOUNT))
    return usdt, stars