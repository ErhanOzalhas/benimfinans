from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import date
import pandas as pd

DB_PATH = Path('data/benimfinans.db')
DB_PATH.parent.mkdir(exist_ok=True)


def connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    con = connect(); cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        symbol TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        currency TEXT DEFAULT 'TRY',
        manual_price_try REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        archived INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_date TEXT NOT NULL,
        asset_symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        quantity REAL NOT NULL,
        price_try REAL NOT NULL,
        commission_try REAL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS price_cache (
        symbol TEXT PRIMARY KEY,
        price_try REAL,
        source TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    # lightweight migrations
    cols = [r[1] for r in cur.execute('PRAGMA table_info(assets)').fetchall()]
    if 'archived' not in cols:
        cur.execute('ALTER TABLE assets ADD COLUMN archived INTEGER DEFAULT 0')
    con.commit(); con.close()
    migrate_csv_if_empty()


def migrate_csv_if_empty():
    con = connect()
    n = pd.read_sql_query('SELECT COUNT(*) AS n FROM assets', con).iloc[0]['n']
    if n == 0 and Path('portfolio.csv').exists():
        df = pd.read_csv('portfolio.csv')
        if not df.empty:
            for _, r in df.iterrows():
                sym = str(r.get('symbol','')).strip().upper()
                if not sym:
                    continue
                con.execute('INSERT OR IGNORE INTO assets(name,symbol,category,manual_price_try) VALUES(?,?,?,?)',
                            (r.get('name', sym), sym, r.get('category','Diğer'), float(r.get('manual_price_try',0) or 0)))
                qty = float(r.get('quantity',0) or 0)
                if qty:
                    con.execute('INSERT INTO transactions(tx_date,asset_symbol,action,quantity,price_try,commission_try,note) VALUES(?,?,?,?,?,?,?)',
                                (str(date.today()), sym, 'Açılış', qty, 0, 0, 'CSV aktarımı'))
            con.commit()
    con.close()


def assets_df(active_only=True, include_archived=False):
    con = connect()
    where=[]
    if active_only:
        where.append('active=1')
    if not include_archived:
        where.append('COALESCE(archived,0)=0')
    q = 'SELECT * FROM assets'
    if where:
        q += ' WHERE ' + ' AND '.join(where)
    q += ' ORDER BY category,name'
    df = pd.read_sql_query(q, con); con.close(); return df


def transactions_df(symbol=None):
    con = connect()
    q = '''SELECT t.*, a.name, a.category FROM transactions t
           LEFT JOIN assets a ON a.symbol=t.asset_symbol'''
    params=[]
    if symbol:
        q += ' WHERE t.asset_symbol=?'; params.append(symbol)
    q += ' ORDER BY tx_date DESC, id DESC'
    df = pd.read_sql_query(q, con, params=params); con.close(); return df


def add_asset(name, symbol, category, currency='TRY', manual_price_try=0):
    sym=symbol.strip().upper()
    con = connect()
    con.execute('''INSERT OR IGNORE INTO assets(name,symbol,category,currency,manual_price_try,active,archived)
                   VALUES(?,?,?,?,?,1,0)''',
                (name.strip(), sym, category, currency, float(manual_price_try or 0)))
    con.execute('UPDATE assets SET active=1, archived=0 WHERE symbol=?', (sym,))
    con.commit(); con.close()


def update_asset(symbol, name, category, manual_price_try, active=1):
    con = connect()
    con.execute('UPDATE assets SET name=?, category=?, manual_price_try=?, active=? WHERE symbol=?',
                (name, category, float(manual_price_try or 0), int(active), symbol))
    con.commit(); con.close()


def archive_asset(symbol):
    con=connect(); con.execute('UPDATE assets SET archived=1, active=0 WHERE symbol=?', (symbol,)); con.commit(); con.close()


def restore_asset(symbol):
    con=connect(); con.execute('UPDATE assets SET archived=0, active=1 WHERE symbol=?', (symbol,)); con.commit(); con.close()


def delete_asset(symbol, delete_transactions=True):
    con=connect()
    if delete_transactions:
        con.execute('DELETE FROM transactions WHERE asset_symbol=?', (symbol,))
    con.execute('DELETE FROM price_cache WHERE symbol=?', (symbol,))
    con.execute('DELETE FROM assets WHERE symbol=?', (symbol,))
    con.commit(); con.close()


def add_transaction(tx_date, symbol, action, quantity, price_try, commission_try=0, note=''):
    con = connect()
    con.execute('INSERT INTO transactions(tx_date,asset_symbol,action,quantity,price_try,commission_try,note) VALUES(?,?,?,?,?,?,?)',
                (str(tx_date), symbol, action, float(quantity), float(price_try), float(commission_try or 0), note or ''))
    con.commit(); con.close()


def delete_transaction(tx_id):
    con = connect(); con.execute('DELETE FROM transactions WHERE id=?', (int(tx_id),)); con.commit(); con.close()


def save_price(symbol, price_try, source):
    con = connect()
    con.execute('INSERT OR REPLACE INTO price_cache(symbol,price_try,source,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)',
                (symbol, float(price_try), source))
    con.commit(); con.close()


def price_cache_df():
    con = connect(); df = pd.read_sql_query('SELECT * FROM price_cache', con); con.close(); return df


def clear_all_data():
    con = connect(); cur=con.cursor()
    cur.execute('DELETE FROM transactions')
    cur.execute('DELETE FROM price_cache')
    cur.execute('DELETE FROM assets')
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('assets','transactions')")
    con.commit(); con.close()
