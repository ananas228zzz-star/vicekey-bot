T = {
    "ru": {
        "start": "Добро пожаловать в VICEKEYS 🎮\nКлючи GTA VI для PS5 и Xbox со скидкой 20%.\nСразу после оплаты мы пришлём вам ключ.",
        "key_ok": "✅ Оплата подтверждена!\n\n{name}\nПлатформа: {platform}, регион: {region}\n\nВаш ключ:\n<code>{key}</code>\n\nОн также сохранён в Mini App во вкладке «Мои ключи».",
        "no_stock": "✅ Оплата получена. Ключ выдадим вручную в ближайшее время, поддержка уже уведомлена.",
        "rejected": "❌ Платёж по заказу #{id} не подтверждён. Если вы оплатили, напишите в поддержку.",
        "open": "🎮 Открыть магазин",
    },
    "en": {
        "start": "Welcome to VICEKEYS 🎮\nGTA VI keys for PS5 and Xbox with 20% off.\nRight after payment we will send you the key.",
        "key_ok": "✅ Payment confirmed!\n\n{name}\nPlatform: {platform}, region: {region}\n\nYour key:\n<code>{key}</code>\n\nIt is also saved in the Mini App under “My keys”.",
        "no_stock": "✅ Payment received. We will issue the key manually shortly, support has been notified.",
        "rejected": "❌ Payment for order #{id} was not confirmed. If you paid, contact support.",
        "open": "🎮 Open store",
    },
}


def tr(lang):
    return T["en"] if lang == "en" else T["ru"]