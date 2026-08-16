import aiosqlite
from datetime import datetime
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    client_name TEXT DEFAULT '',
    client_phone TEXT DEFAULT '',
    car_make TEXT DEFAULT '',
    car_model TEXT DEFAULT '',
    car_plate TEXT DEFAULT '',
    car_vin TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',  -- draft / in_progress / completed
    paid_amount INTEGER NOT NULL DEFAULT 0,
    appointment_date TEXT NOT NULL DEFAULT '',   -- 'YYYY-MM-DD'
    appointment_time TEXT NOT NULL DEFAULT '',   -- 'HH:MM'
    reminder_day_sent INTEGER NOT NULL DEFAULT 0,
    reminder_hour_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS dents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    element TEXT NOT NULL,
    technology TEXT NOT NULL,
    complexity TEXT NOT NULL,
    material TEXT NOT NULL,
    car_class TEXT NOT NULL,
    width_cm REAL NOT NULL DEFAULT 0,
    length_cm REAL NOT NULL DEFAULT 0,
    price INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_master_status ON orders(master_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_appointment ON orders(appointment_date, status);
CREATE INDEX IF NOT EXISTS idx_dents_order ON dents(order_id);

CREATE TABLE IF NOT EXISTS masters (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # WAL — швидші читання/записи і менше шансів на "database is locked",
        # коли фоновий цикл нагадувань читає базу одночасно з тим, як майстер
        # щось зберігає в боті.
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA synchronous = NORMAL")

        await db.executescript(SCHEMA)
        # Легка міграція: якщо база створена старою версією бота —
        # додаємо нові колонки, не втрачаючи існуючі дані.
        cur = await db.execute("PRAGMA table_info(dents)")
        cols = {row[1] for row in await cur.fetchall()}
        if "width_cm" not in cols:
            await db.execute("ALTER TABLE dents ADD COLUMN width_cm REAL NOT NULL DEFAULT 0")
        if "length_cm" not in cols:
            await db.execute("ALTER TABLE dents ADD COLUMN length_cm REAL NOT NULL DEFAULT 0")

        cur = await db.execute("PRAGMA table_info(orders)")
        order_cols = {row[1] for row in await cur.fetchall()}
        for col, ddl in (
            ("appointment_date", "ALTER TABLE orders ADD COLUMN appointment_date TEXT NOT NULL DEFAULT ''"),
            ("appointment_time", "ALTER TABLE orders ADD COLUMN appointment_time TEXT NOT NULL DEFAULT ''"),
            ("reminder_day_sent", "ALTER TABLE orders ADD COLUMN reminder_day_sent INTEGER NOT NULL DEFAULT 0"),
            ("reminder_hour_sent", "ALTER TABLE orders ADD COLUMN reminder_hour_sent INTEGER NOT NULL DEFAULT 0"),
        ):
            if col not in order_cols:
                await db.execute(ddl)
        await db.commit()


# ---------- orders ----------

async def create_order(master_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (master_id, status, created_at) VALUES (?, 'draft', ?)",
            (master_id, datetime.now().isoformat(timespec="seconds")),
        )
        await db.commit()
        return cur.lastrowid


async def update_order_field(order_id: int, field: str, value):
    assert field in {
        "client_name", "client_phone", "car_make", "car_model",
        "car_plate", "car_vin", "status", "paid_amount", "completed_at",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (value, order_id))
        await db.commit()


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_orders(master_id: int, status: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE master_id = ? AND status = ? ORDER BY id DESC",
            (master_id, status),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM dents WHERE order_id = ?", (order_id,))
        await db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        await db.commit()


# ---------- dents ----------

async def add_dent(order_id: int, element: str, technology: str, complexity: str,
                    material: str, car_class: str, price: int,
                    width_cm: float = 0, length_cm: float = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO dents (order_id, element, technology, complexity, material, car_class,
                                   width_cm, length_cm, price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, element, technology, complexity, material, car_class, width_cm, length_cm, price),
        )
        await db.commit()
        return cur.lastrowid


async def list_dents(order_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM dents WHERE order_id = ? ORDER BY id", (order_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_dent(dent_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM dents WHERE id = ?", (dent_id,))
        await db.commit()


async def order_total(order_id: int) -> int:
    dents = await list_dents(order_id)
    return sum(d["price"] for d in dents)


# ---------- запис на дату/час ----------

async def set_appointment(order_id: int, date_str: str, time_str: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET appointment_date = ?, appointment_time = ?,
                                  reminder_day_sent = 0, reminder_hour_sent = 0
               WHERE id = ?""",
            (date_str, time_str, order_id),
        )
        await db.commit()


async def clear_appointment(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET appointment_date = '', appointment_time = '',
                                  reminder_day_sent = 0, reminder_hour_sent = 0
               WHERE id = ?""",
            (order_id,),
        )
        await db.commit()


async def list_orders_by_date(master_id: int, date_str: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM orders WHERE master_id = ? AND appointment_date = ?
               ORDER BY appointment_time""",
            (master_id, date_str),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_scheduled_orders_for_reminders() -> list[dict]:
    """Усі активні замовлення з призначеним записом — для фонового нагадувача."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM orders
               WHERE status = 'in_progress' AND appointment_date != '' AND appointment_time != ''"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def mark_reminder_sent(order_id: int, field: str):
    assert field in {"reminder_day_sent", "reminder_hour_sent"}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE orders SET {field} = 1 WHERE id = ?", (order_id,))
        await db.commit()


# ---------- доступ майстрів ----------

async def is_master(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM masters WHERE user_id = ? LIMIT 1", (user_id,))
        return await cur.fetchone() is not None


async def add_master(user_id: int, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO masters (user_id, added_by, created_at) VALUES (?, ?, ?)",
            (user_id, added_by, datetime.now().isoformat(timespec="seconds")),
        )
        await db.commit()


async def remove_master(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE user_id = ?", (user_id,))
        await db.commit()


async def list_masters() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM masters ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
