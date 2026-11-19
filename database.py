import aiosqlite
from datetime import datetime

from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS keys(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edition TEXT NOT NULL,
                platform TEXT NOT NULL,
                region TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                order_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                edition TEXT NOT NULL,
                platform TEXT NOT NULL,
                region TEXT NOT NULL,
                method TEXT NOT NULL,
                usdt REAL NOT NULL,
                stars INTEGER NOT NULL,
                status TEXT NOT NULL,
                key TEXT,
                lang TEXT NOT NULL DEFAULT 'ru',
                created TEXT NOT NULL
            );
            """
        )
        await db.commit()


async def add_keys(edition, platform, region, keys):
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for k in keys:
            cur = await db.execute(
                "INSERT OR IGNORE INTO keys(edition, platform, region, key) VALUES(?,?,?,?)",
                (edition, platform, region, k),
            )
            added += cur.rowcount
        await db.commit()
    return added


async def stock_map():
    result = {}
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT platform, edition, region, COUNT(*) FROM keys WHERE order_id IS NULL GROUP BY platform, edition, region"
        )
        for platform, edition, region, n in await cur.fetchall():
            result.setdefault(platform, {}).setdefault(edition, {})[region] = n
    return result


async def stock_count(edition, platform, region):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM keys WHERE edition=? AND platform=? AND region=? AND order_id IS NULL",
            (edition, platform, region),
        )
        return (await cur.fetchone())[0]


async def create_order(user_id, edition, platform, region, method, usdt, stars, lang):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders(user_id, edition, platform, region, method, usdt, stars, status, lang, created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user_id, edition, platform, region, method, usdt, stars, "new", lang, datetime.utcnow().strftime("%d.%m.%Y")),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_status(order_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        await db.commit()


async def user_orders(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, edition, platform, region, status, key, created FROM orders WHERE user_id=? AND status IN ('issued','pending_review','paid','paid_no_stock') ORDER BY id DESC LIMIT 50",
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def issue_key(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.isolation_level = None
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT edition, platform, region, key FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()
        if not order:
            await db.execute("ROLLBACK")
            return None
        if order[3]:
            await db.execute("COMMIT")
            return order[3]
        cur = await db.execute(
            "SELECT id, key FROM keys WHERE edition=? AND platform=? AND region=? AND order_id IS NULL LIMIT 1",
            (order[0], order[1], order[2]),
        )
        item = await cur.fetchone()
        if not item:
            await db.execute("ROLLBACK")
            return None
        await db.execute("UPDATE keys SET order_id=? WHERE id=?", (order_id, item[0]))
        await db.execute("UPDATE orders SET status='issued', key=? WHERE id=?", (item[1], order_id))
        await db.execute("COMMIT")
        return item[1]