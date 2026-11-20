from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
import os
import sqlite3

FORMATS = ("Фільм", "Серіал")
STATES = ("Хочу подивитися", "Дивлюся", "Переглянуто")
GENRES = ("Комедія", "Драма", "Фантастика", "Детектив", "Анімація")
SEED = (
    ("Готель «Ґранд Будапешт»", 2014, "Фільм", 1, STATES[0], None),
    ("Інтерстеллар", 2014, "Фільм", 3, STATES[2], 9),
    ("Тед Лассо", 2020, "Серіал", 1, STATES[1], None),
    ("Шерлок", 2010, "Серіал", 4, STATES[2], 8),
    ("Думками навиворіт", 2015, "Фільм", 5, STATES[0], None),
    ("Ведмідь", 2022, "Серіал", 2, STATES[1], None),
)


@contextmanager
def connection():
    path = Path(os.getenv("WATCHLIST_DB") or Path(__file__).with_name("watchlist.sqlite3"))
    with closing(sqlite3.connect(path, timeout=10)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.create_function("fold", 1, str.casefold)
        with con:
            yield con


def initialize():
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("PRAGMA user_version").fetchone()[0] == 1:
            return
        con.execute("CREATE TABLE genres (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        con.execute("""
            CREATE TABLE titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
                year INTEGER NOT NULL CHECK(year >= 1888),
                kind TEXT NOT NULL CHECK(kind IN ('Фільм', 'Серіал')),
                genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE RESTRICT,
                status TEXT NOT NULL CHECK(status IN ('Хочу подивитися','Дивлюся','Переглянуто')),
                rating INTEGER CHECK(rating BETWEEN 1 AND 10),
                CHECK(rating IS NULL OR status = 'Переглянуто')
            )
        """)
        con.executemany("INSERT INTO genres(name) VALUES (?)", [(g,) for g in GENRES])
        con.executemany("""
            INSERT INTO titles(name,year,kind,genre_id,status,rating) VALUES (?,?,?,?,?,?)
        """, SEED)
        con.execute("PRAGMA user_version = 1")


def genres():
    with connection() as con:
        return {r["name"]: r["id"] for r in con.execute("SELECT * FROM genres ORDER BY name")}


def titles(query="", genre=None, status=None):
    with connection() as con:
        return [dict(r) for r in con.execute("""
            SELECT t.*, g.name AS genre FROM titles AS t
            JOIN genres AS g ON g.id = t.genre_id
            WHERE instr(fold(t.name), fold(?)) > 0
              AND (? IS NULL OR t.genre_id = ?) AND (? IS NULL OR t.status = ?)
            ORDER BY fold(t.name), t.year, t.id
        """, (query.strip(), genre, genre, status, status))]


def save(name, year, kind, genre_id, status, rating=None, record_id=None):
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("Введіть назву завдовжки від 1 до 120 символів.")
    if not 1888 <= year <= date.today().year + 1:
        raise ValueError("Перевірте рік виходу.")
    if kind not in FORMATS or status not in STATES:
        raise ValueError("Виберіть формат і статус зі списку.")
    if rating is not None and (status != STATES[2] or rating not in range(1, 11)):
        raise ValueError("Оцінку від 1 до 10 можна ставити після перегляду.")
    values = (name, year, kind, genre_id, status, rating)
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        if not con.execute("SELECT 1 FROM genres WHERE id=?", (genre_id,)).fetchone():
            raise ValueError("Такого жанру немає.")
        if con.execute("""
            SELECT 1 FROM titles WHERE fold(name)=fold(?) AND year=? AND kind=? AND id IS NOT ?
        """, (name, year, kind, record_id)).fetchone():
            raise ValueError("Такий запис уже є у списку.")
        if record_id is None:
            return con.execute("""
                INSERT INTO titles(name,year,kind,genre_id,status,rating) VALUES (?,?,?,?,?,?)
            """, values).lastrowid
        cursor = con.execute("""
            UPDATE titles SET name=?,year=?,kind=?,genre_id=?,status=?,rating=? WHERE id=?
        """, (*values, record_id))
        if not cursor.rowcount:
            raise ValueError("Запис уже видалено. Оновіть список.")
        return record_id


def remove(record_id):
    with connection() as con:
        if not con.execute("DELETE FROM titles WHERE id=?", (record_id,)).rowcount:
            raise ValueError("Запис уже видалено.")
