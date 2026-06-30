from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from datetime import date
import pandas as pd

DB_PATH = Path('data/benimfinans.db')
DB_PATH.parent.mkdir(exist_ok=True)

# ------------------------------------------------------------
# Benim Finans DB Router
# ------------------------------------------------------------
# Streamlit Cloud'da SUPABASE_URL ve SUPABASE_KEY secrets olarak girilirse
# tüm veri Supabase'e yazılır. Secrets yoksa yerel geliştirme için SQLite kullanılır.


def _get_secret(name: str, default: str = '') -> str:
    val = os.getenv(name, '')
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return default


def using_supabase() -> bool:
    return bool(_get_secret('SUPABASE_URL') and (_get_secret('SUPABASE_ANON_KEY') or _get_secret('SUPABASE_KEY')))


def _supabase_client():
    from supabase import create_client
    return create_client(_get_secret('SUPABASE_URL'), _get_secret('SUPABASE_ANON_KEY') or _get_secret('SUPABASE_KEY'))


def backend_name() -> str:
    return 'Supabase Cloud' if using_supabase() else 'SQLite Local'


# ------------------------------------------------------------
# SQLite fallback
# ------------------------------------------------------------

def connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _sqlite_init_db():
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
    cols = [r[1] for r in cur.execute('PRAGMA table_info(assets)').fetchall()]
    if 'archived' not in cols:
        cur.execute('ALTER TABLE assets ADD COLUMN archived INTEGER DEFAULT 0')
    con.commit(); con.close()
    _sqlite_migrate_csv_if_empty()


def _sqlite_migrate_csv_if_empty():
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


# ------------------------------------------------------------
# Public API used by app.py and portfolio_engine.py
# ------------------------------------------------------------

def init_db():
    if using_supabase():
        # Supabase tabloları docs/supabase_schema.sql ile bir kere oluşturulmalı.
        return
    _sqlite_init_db()


def assets_df(active_only=True, include_archived=False):
    if using_supabase():
        sb = _supabase_client()
        q = sb.table('assets').select('*')
        if active_only:
            q = q.eq('active', True)
        if not include_archived:
            q = q.eq('archived', False)
        res = q.order('category').order('name').execute()
        return pd.DataFrame(res.data or [])
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
    if using_supabase():
        sb = _supabase_client()
        q = sb.table('transactions').select('*')
        if symbol:
            q = q.eq('asset_symbol', symbol)
        res = q.order('tx_date', desc=True).order('id', desc=True).execute()
        tx = pd.DataFrame(res.data or [])
        if tx.empty:
            return pd.DataFrame(columns=['id','tx_date','asset_symbol','action','quantity','price_try','commission_try','note','created_at','name','category'])
        assets = assets_df(active_only=False, include_archived=True)
        if not assets.empty:
            tx = tx.merge(assets[['symbol','name','category']], left_on='asset_symbol', right_on='symbol', how='left').drop(columns=['symbol'], errors='ignore')
        else:
            tx['name'] = tx['asset_symbol']; tx['category'] = ''
        return tx
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
    if using_supabase():
        sb = _supabase_client()
        sb.table('assets').upsert({
            'name': name.strip(), 'symbol': sym, 'category': category, 'currency': currency,
            'manual_price_try': float(manual_price_try or 0), 'active': True, 'archived': False
        }, on_conflict='symbol').execute()
        return
    con = connect()
    con.execute('''INSERT OR IGNORE INTO assets(name,symbol,category,currency,manual_price_try,active,archived)
                   VALUES(?,?,?,?,?,1,0)''',
                (name.strip(), sym, category, currency, float(manual_price_try or 0)))
    con.execute('UPDATE assets SET name=?, category=?, manual_price_try=?, active=1, archived=0 WHERE symbol=?',
                (name.strip(), category, float(manual_price_try or 0), sym))
    con.commit(); con.close()


def update_asset(symbol, name, category, manual_price_try, active=1):
    if using_supabase():
        _supabase_client().table('assets').update({
            'name': name, 'category': category, 'manual_price_try': float(manual_price_try or 0), 'active': bool(active)
        }).eq('symbol', symbol).execute(); return
    con = connect()
    con.execute('UPDATE assets SET name=?, category=?, manual_price_try=?, active=? WHERE symbol=?',
                (name, category, float(manual_price_try or 0), int(active), symbol))
    con.commit(); con.close()


def archive_asset(symbol):
    if using_supabase():
        _supabase_client().table('assets').update({'archived': True, 'active': False}).eq('symbol', symbol).execute(); return
    con=connect(); con.execute('UPDATE assets SET archived=1, active=0 WHERE symbol=?', (symbol,)); con.commit(); con.close()


def restore_asset(symbol):
    if using_supabase():
        _supabase_client().table('assets').update({'archived': False, 'active': True}).eq('symbol', symbol).execute(); return
    con=connect(); con.execute('UPDATE assets SET archived=0, active=1 WHERE symbol=?', (symbol,)); con.commit(); con.close()


def delete_asset(symbol, delete_transactions=True):
    if using_supabase():
        sb = _supabase_client()
        if delete_transactions:
            sb.table('transactions').delete().eq('asset_symbol', symbol).execute()
        sb.table('price_cache').delete().eq('symbol', symbol).execute()
        sb.table('assets').delete().eq('symbol', symbol).execute()
        return
    con=connect()
    if delete_transactions:
        con.execute('DELETE FROM transactions WHERE asset_symbol=?', (symbol,))
    con.execute('DELETE FROM price_cache WHERE symbol=?', (symbol,))
    con.execute('DELETE FROM assets WHERE symbol=?', (symbol,))
    con.commit(); con.close()


def add_transaction(tx_date, symbol, action, quantity, price_try, commission_try=0, note=''):
    row = {'tx_date': str(tx_date), 'asset_symbol': symbol, 'action': action,
           'quantity': float(quantity), 'price_try': float(price_try),
           'commission_try': float(commission_try or 0), 'note': note or ''}
    if using_supabase():
        _supabase_client().table('transactions').insert(row).execute(); return
    con = connect()
    con.execute('INSERT INTO transactions(tx_date,asset_symbol,action,quantity,price_try,commission_try,note) VALUES(?,?,?,?,?,?,?)',
                (row['tx_date'], row['asset_symbol'], row['action'], row['quantity'], row['price_try'], row['commission_try'], row['note']))
    con.commit(); con.close()


def delete_transaction(tx_id):
    if using_supabase():
        _supabase_client().table('transactions').delete().eq('id', int(tx_id)).execute(); return
    con = connect(); con.execute('DELETE FROM transactions WHERE id=?', (int(tx_id),)); con.commit(); con.close()


def save_price(symbol, price_try, source):
    if using_supabase():
        _supabase_client().table('price_cache').upsert({
            'symbol': symbol, 'price_try': float(price_try), 'source': source
        }, on_conflict='symbol').execute(); return
    con = connect()
    con.execute('INSERT OR REPLACE INTO price_cache(symbol,price_try,source,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)',
                (symbol, float(price_try), source))
    con.commit(); con.close()


def price_cache_df():
    if using_supabase():
        res = _supabase_client().table('price_cache').select('*').execute()
        return pd.DataFrame(res.data or [])
    con = connect(); df = pd.read_sql_query('SELECT * FROM price_cache', con); con.close(); return df


def clear_all_data():
    if using_supabase():
        sb = _supabase_client()
        # Supabase delete needs a filter; id >= 0 covers all generated rows.
        sb.table('transactions').delete().gte('id', 0).execute()
        sb.table('price_cache').delete().neq('symbol', '__never__').execute()
        sb.table('assets').delete().gte('id', 0).execute()
        return
    con = connect(); cur=con.cursor()
    cur.execute('DELETE FROM transactions')
    cur.execute('DELETE FROM price_cache')
    cur.execute('DELETE FROM assets')
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('assets','transactions')")
    con.commit(); con.close()


# ------------------------------------------------------------
# Daily snapshots — portfolio history
# ------------------------------------------------------------
def save_snapshot(total_value_try: float, total_pl_try: float = 0, note: str = ''):
    today = str(date.today())
    row = {'snapshot_date': today, 'total_value_try': float(total_value_try or 0), 'total_pl_try': float(total_pl_try or 0), 'note': note or ''}
    if using_supabase():
        _supabase_client().table('daily_snapshots').upsert(row, on_conflict='snapshot_date').execute(); return
    con = connect()
    con.execute("""CREATE TABLE IF NOT EXISTS daily_snapshots (
        snapshot_date TEXT PRIMARY KEY,
        total_value_try REAL DEFAULT 0,
        total_pl_try REAL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.execute('INSERT OR REPLACE INTO daily_snapshots(snapshot_date,total_value_try,total_pl_try,note) VALUES(?,?,?,?)',
                (row['snapshot_date'], row['total_value_try'], row['total_pl_try'], row['note']))
    con.commit(); con.close()


def snapshots_df():
    if using_supabase():
        res = _supabase_client().table('daily_snapshots').select('*').order('snapshot_date').execute()
        return pd.DataFrame(res.data or [])
    con = connect()
    con.execute("""CREATE TABLE IF NOT EXISTS daily_snapshots (
        snapshot_date TEXT PRIMARY KEY,
        total_value_try REAL DEFAULT 0,
        total_pl_try REAL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    df = pd.read_sql_query('SELECT * FROM daily_snapshots ORDER BY snapshot_date', con); con.close(); return df
