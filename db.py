# -*- coding: utf-8 -*-
"""Qurilish Radar — mahalliy baza (topilgan obyektlar + takrorlanmaslik)."""
import os
import sqlite3
import datetime as dt
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "radar.db"

TZ = dt.timezone(dt.timedelta(hours=5))  # Toshkent


def now_tk():
    return dt.datetime.now(TZ)


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = _con()
    con.execute("""CREATE TABLE IF NOT EXISTS topilgan(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kalit TEXT UNIQUE,
        manba TEXT, nom TEXT, url TEXT,
        joy TEXT, quruvchi TEXT, holat TEXT, sana TEXT, rasm TEXT,
        yuborildi INTEGER DEFAULT 0,
        created TEXT
    )""")
    con.commit()
    con.close()


def yangi_mi(kalit):
    """Shu obyekt ilgari topilganmi? (takror yubormaslik uchun)"""
    con = _con()
    r = con.execute("SELECT 1 FROM topilgan WHERE kalit=?", (kalit,)).fetchone()
    con.close()
    return r is None


def qosh(item):
    """Yangi obyektni saqlaydi. Qaytadi: True (yangi) / False (allaqachon bor)."""
    con = _con()
    try:
        con.execute("""INSERT INTO topilgan(kalit,manba,nom,url,joy,quruvchi,holat,sana,rasm,created)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (item.get("kalit"), item.get("manba"), item.get("nom"), item.get("url"),
                     item.get("joy"), item.get("quruvchi"), item.get("holat"),
                     item.get("sana"), item.get("rasm"), now_tk().isoformat()))
        con.commit()
        yangi = True
    except sqlite3.IntegrityError:
        yangi = False
    con.close()
    return yangi


def yuborildi_belgila(kalit):
    con = _con()
    con.execute("UPDATE topilgan SET yuborildi=1 WHERE kalit=?", (kalit,))
    con.commit()
    con.close()


def oxirgilar(n=20):
    con = _con()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM topilgan ORDER BY id DESC LIMIT ?", (n,)).fetchall()]
    con.close()
    return rows


def jami():
    con = _con()
    n = con.execute("SELECT COUNT(*) FROM topilgan").fetchone()[0]
    con.close()
    return n


def tozala():
    """Barcha topilgan yozuvlarni o'chiradi. Qaytadi: o'chirilgan soni."""
    con = _con()
    n = con.execute("SELECT COUNT(*) FROM topilgan").fetchone()[0]
    con.execute("DELETE FROM topilgan")
    con.commit()
    con.close()
    return n
