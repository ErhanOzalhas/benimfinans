from __future__ import annotations

import sqlite3
from datetime import datetime, date
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "benimfinans.db"
PORTFOLIO_CSV = BASE_DIR / "portfolio.csv"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = connect(); cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        cost_try REAL NOT NULL DEFAULT 0,
        manual_price_try REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        asset TEXT NOT NULL,
        action TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        price_try REAL NOT NULL DEFAULT 0,
        note TEXT DEFAULT ''
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        total_try REAL NOT NULL,
        details_json TEXT DEFAULT ''
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset TEXT NOT NULL,
        operator TEXT NOT NULL,
        target_price REAL NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)
    con.commit()
    count = cur.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
    if count == 0 and PORTFOLIO_CSV.exists():
        seed_assets_from_csv(PORTFOLIO_CSV)
    con.close()


def seed_assets_from_csv(path: Path) -> None:
    con = connect(); cur = con.cursor()
    df = pd.read_csv(path)
    now = datetime.now().isoformat(timespec="seconds")
    for _, r in df.iterrows():
        cur.execute(
            "INSERT INTO assets(name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?)",
            (str(r["name"]), str(r["symbol"]), str(r["category"]), float(r["quantity"]), float(r.get("cost_try",0) or 0), float(r.get("manual_price_try",0) or 0), now),
        )
    con.commit(); con.close()


def load_assets() -> pd.DataFrame:
    con = connect()
    df = pd.read_sql_query("SELECT * FROM assets ORDER BY category, name", con)
    con.close()
    return df


def save_assets(df: pd.DataFrame) -> None:
    con = connect(); cur = con.cursor()
    cur.execute("DELETE FROM assets")
    now = datetime.now().isoformat(timespec="seconds")
    for _, r in df.iterrows():
        cur.execute(
            "INSERT INTO assets(id,name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (int(r["id"]) if str(r.get("id", "")).strip() not in ["", "nan", "None"] else None,
             str(r["name"]), str(r["symbol"]).upper().strip(), str(r["category"]),
             float(r.get("quantity",0) or 0), float(r.get("cost_try",0) or 0), float(r.get("manual_price_try",0) or 0), str(r.get("created_at") or now)),
        )
    con.commit(); con.close()


def add_asset(name: str, symbol: str, category: str, quantity: float, cost_try: float, manual_price_try: float) -> None:
    con = connect(); cur = con.cursor()
    cur.execute(
        "INSERT INTO assets(name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?)",
        (name, symbol.upper().strip(), category, quantity, cost_try, manual_price_try, datetime.now().isoformat(timespec="seconds")),
    )
    con.commit(); con.close()


def delete_asset(asset_id: int) -> None:
    con = connect(); cur = con.cursor()
    cur.execute("DELETE FROM assets WHERE id=?", (asset_id,))
    con.commit(); con.close()


def add_transaction(asset: str, action: str, quantity: float, price_try: float, note: str) -> None:
    con = connect(); cur = con.cursor()
    cur.execute("INSERT INTO transactions(date,asset,action,quantity,price_try,note) VALUES(?,?,?,?,?,?)", (date.today().isoformat(), asset, action, quantity, price_try, note))
    if action in ["Alış", "Satış"]:
        sign = 1 if action == "Alış" else -1
        cur.execute("UPDATE assets SET quantity = quantity + ? WHERE name = ? OR symbol = ?", (sign * quantity, asset, asset))
        if action == "Alış" and price_try > 0:
            cur.execute("UPDATE assets SET cost_try = ? WHERE name = ? OR symbol = ?", (price_try, asset, asset))
    con.commit(); con.close()


def load_transactions() -> pd.DataFrame:
    con = connect(); df = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", con); con.close(); return df


def add_snapshot(total_try: float, details_json: str = "") -> None:
    con = connect(); cur = con.cursor()
    cur.execute("INSERT INTO snapshots(ts,total_try,details_json) VALUES(?,?,?)", (datetime.now().isoformat(timespec="seconds"), float(total_try), details_json))
    con.commit(); con.close()


def load_snapshots() -> pd.DataFrame:
    con = connect(); df = pd.read_sql_query("SELECT * FROM snapshots ORDER BY ts", con); con.close(); return df


def add_alert(asset: str, operator: str, target_price: float) -> None:
    con = connect(); cur = con.cursor()
    cur.execute("INSERT INTO alerts(asset,operator,target_price,active,created_at) VALUES(?,?,?,?,?)", (asset, operator, target_price, 1, datetime.now().isoformat(timespec="seconds")))
    con.commit(); con.close()


def load_alerts() -> pd.DataFrame:
    con = connect(); df = pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC", con); con.close(); return df
