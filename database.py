"""
Зберігання заявок клієнтів у SQLite через aiosqlite.
"""
import aiosqlite
from config import DB_PATH

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    brand TEXT,
    model TEXT,
    year INTEGER,
    damage_type TEXT,
    damage_size TEXT,
    extra_works TEXT,
    total_price INTEGER,
    phone TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def save_request(user_id: int, username: str, brand: str, model: str,
                        year: int, damage_type: str, damage_size: str,
                        extra_works: str, total_price: int, phone: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO requests
               (user_id, username, brand, model, year, damage_type,
                damage_size, extra_works, total_price, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, brand, model, year, damage_type,
             damage_size, extra_works, total_price, phone),
        )
        await db.commit()
        return cursor.lastrowid
