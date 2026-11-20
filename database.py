import time

import aiosqlite
from datetime import datetime

import config
from config import DB_PATH


def now():
    return datetime.utcnow().strftime("%d.%m.%Y %H:%M")


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
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                referrer_id INTEGER,
                percent REAL,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS referral_earnings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL UNIQUE,
                referrer_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                order_usdt REAL NOT NULL,
                percent REAL NOT NULL,
                commission REAL NOT NULL,
                status TEXT NOT NULL,
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);
            CREATE INDEX IF NOT EXISTS idx_earn_referrer ON referral_earnings(referrer_id);
            INSERT OR IGNORE INTO users(user_id, created) SELECT DISTINCT user_id, 'migrated' FROM orders;
            """
        )
        cur = await db.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in await cur.fetchall()]
        if "username" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "last_activity" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN last_activity INTEGER")
            await db.execute("ALTER TABLE users ADD COLUMN reminder_stage INTEGER NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN has_purchased INTEGER NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN last_reminder_at INTEGER")
            await db.execute("UPDATE users SET last_activity=?", (int(time.time()),))
            await db.execute(
                "UPDATE users SET has_purchased=1 WHERE user_id IN (SELECT user_id FROM orders WHERE status IN ('issued','paid','paid_no_stock'))"
            )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(lower(username))")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_remind ON users(has_purchased, is_blocked, reminder_stage, last_activity)"
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
    async with aiosqlite.connect(DB_PATH, isolation_level=None) as db:
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


async def register_user(user_id, referrer_id=None, username=None):
    uname = username.lstrip("@") if username else None
    async with aiosqlite.connect(DB_PATH) as db:
        if uname:
            await db.execute(
                "UPDATE users SET username=NULL WHERE lower(username)=lower(?) AND user_id!=?",
                (uname, user_id),
            )
        cur = await db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        if await cur.fetchone():
            if uname:
                await db.execute(
                    "UPDATE users SET username=? WHERE user_id=? AND (username IS NULL OR username!=?)",
                    (uname, user_id, uname),
                )
            await db.commit()
            return False
        ref = None
        if referrer_id and referrer_id != user_id:
            cur = await db.execute("SELECT 1 FROM users WHERE user_id=?", (referrer_id,))
            if await cur.fetchone():
                ref = referrer_id
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, referrer_id, username, created, last_activity) VALUES(?,?,?,?,?)",
            (user_id, ref, uname, now(), int(time.time())),
        )
        await db.commit()
        return True


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT user_id, username, referrer_id, percent FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def find_user_by_username(username):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id FROM users WHERE lower(username)=lower(?) LIMIT 1",
            (username.lstrip("@"),),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_percent(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT percent FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
    if row and row[0] is not None:
        return float(row[0]), True
    return config.REF_PERCENT, False


async def set_percent(user_id, percent):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users(user_id, percent, created) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET percent=excluded.percent",
            (user_id, percent, now()),
        )
        await db.commit()


async def reset_percent(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET percent=NULL WHERE user_id=?", (user_id,))
        await db.commit()


async def ref_stats(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,))
        invited = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(DISTINCT buyer_id), COUNT(*), COALESCE(SUM(order_usdt),0), COALESCE(SUM(commission),0) FROM referral_earnings WHERE referrer_id=? AND status='accrued'",
            (user_id,),
        )
        buyers, purchases, total, earned = await cur.fetchone()
    return {"invited": invited, "buyers": buyers, "purchases": purchases, "sum": float(total), "earned": float(earned)}


async def accrue_referral(order_id):
    async with aiosqlite.connect(DB_PATH, isolation_level=None) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT user_id, usdt, status FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()
        if not order or order[2] != "issued":
            await db.execute("ROLLBACK")
            return None
        cur = await db.execute("SELECT 1 FROM referral_earnings WHERE order_id=?", (order_id,))
        if await cur.fetchone():
            await db.execute("ROLLBACK")
            return None
        buyer = order[0]
        cur = await db.execute("SELECT referrer_id FROM users WHERE user_id=?", (buyer,))
        row = await cur.fetchone()
        if not row or not row[0] or row[0] == buyer:
            await db.execute("ROLLBACK")
            return None
        referrer = row[0]
        cur = await db.execute("SELECT percent FROM users WHERE user_id=?", (referrer,))
        prow = await cur.fetchone()
        percent = float(prow[0]) if prow and prow[0] is not None else config.REF_PERCENT
        commission = round(order[1] * percent / 100, 2)
        await db.execute(
            "INSERT INTO referral_earnings(order_id, referrer_id, buyer_id, order_usdt, percent, commission, status, created) VALUES(?,?,?,?,?,?,?,?)",
            (order_id, referrer, buyer, order[1], percent, commission, "accrued", now()),
        )
        await db.execute("COMMIT")
        return {"referrer_id": referrer, "commission": commission, "percent": percent}


async def cancel_referral(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE referral_earnings SET status='cancelled' WHERE order_id=? AND status='accrued'",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def touch_activity(user_id, from_bot=False):
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        if from_bot:
            await db.execute(
                "UPDATE users SET last_activity=?, reminder_stage=0, last_reminder_at=NULL, is_blocked=0 WHERE user_id=?",
                (ts, user_id),
            )
        else:
            await db.execute(
                "UPDATE users SET last_activity=?, reminder_stage=0, last_reminder_at=NULL WHERE user_id=? AND (last_activity IS NULL OR last_activity<? OR reminder_stage!=0)",
                (ts, user_id, ts - 60),
            )
        await db.commit()


async def mark_purchased(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET has_purchased=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def set_blocked(user_id, flag):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=? WHERE user_id=?", (1 if flag else 0, user_id))
        await db.commit()


async def due_reminders(now_ts, delays, min_gap, limit):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT u.user_id, u.reminder_stage, u.last_activity FROM users u
            WHERE u.has_purchased=0 AND u.is_blocked=0 AND u.last_activity IS NOT NULL
              AND (
                (u.reminder_stage=0 AND u.last_activity<=?)
                OR (u.reminder_stage=1 AND u.last_activity<=?)
                OR (u.reminder_stage=2 AND u.last_activity<=?)
              )
              AND (u.last_reminder_at IS NULL OR u.last_reminder_at<=?)
              AND NOT EXISTS (
                SELECT 1 FROM orders o WHERE o.user_id=u.user_id
                AND o.status IN ('pending_review','paid','paid_no_stock','issued')
              )
            ORDER BY u.last_activity
            LIMIT ?
            """,
            (now_ts - delays[1], now_ts - delays[2], now_ts - delays[3], now_ts - min_gap, limit),
        )
        return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


async def set_stage(user_id, stage, ts, last_activity):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET reminder_stage=?, last_reminder_at=? WHERE user_id=? AND last_activity=?",
            (stage, ts, user_id, last_activity),
        )
        await db.commit()