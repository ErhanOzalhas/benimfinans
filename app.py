from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

APP_TITLE = "Benim Finans"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "benimfinans.db"
PORTFOLIO_CSV = BASE_DIR / "portfolio.csv"

st.set_page_config(page_title=APP_TITLE, page_icon="💼", layout="wide")

CUSTOM_CSS = """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 3rem; }
[data-testid="stMetricValue"] { font-size: 2rem; }
.card {border:1px solid #e5e7eb; border-radius:18px; padding:18px; background:#fff; box-shadow:0 1px 8px rgba(15,23,42,.04);}
.small-muted {color:#64748b; font-size:.85rem;}
@media (max-width: 768px) {
  [data-testid="column"] { width: 100% !important; flex: unset; }
  [data-testid="stMetricValue"] { font-size: 1.55rem; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

CATEGORY_OPTIONS = ["Altın", "Döviz", "BIST", "ABD Hisse", "Fon", "Kripto", "Diğer"]
CURRENCY_SYMBOLS = {"USDTRY": "Dolar", "EURTRY": "Euro", "GBPTRY": "Sterlin"}


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = db()
    cur = con.cursor()
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
        total_try REAL NOT NULL
    )
    """)
    con.commit()
    # Seed once
    count = cur.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
    if count == 0 and PORTFOLIO_CSV.exists():
        df = pd.read_csv(PORTFOLIO_CSV)
        now = datetime.now().isoformat(timespec="seconds")
        for _, r in df.iterrows():
            cur.execute(
                "INSERT INTO assets(name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?)",
                (str(r["name"]), str(r["symbol"]), str(r["category"]), float(r["quantity"]), float(r.get("cost_try",0) or 0), float(r.get("manual_price_try",0) or 0), now),
            )
        con.commit()
    con.close()


def load_assets() -> pd.DataFrame:
    con = db()
    df = pd.read_sql_query("SELECT * FROM assets ORDER BY id", con)
    con.close()
    return df


def save_assets(df: pd.DataFrame) -> None:
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM assets")
    now = datetime.now().isoformat(timespec="seconds")
    for _, r in df.iterrows():
        cur.execute(
            "INSERT INTO assets(id,name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (int(r["id"]) if pd.notna(r.get("id")) else None, r["name"], r["symbol"], r["category"], float(r["quantity"]), float(r.get("cost_try",0) or 0), float(r.get("manual_price_try",0) or 0), r.get("created_at") or now),
        )
    con.commit(); con.close()


def get_truncgil_rates() -> dict[str, float]:
    # Unofficial public JSON. If it fails, manual/cache values are used.
    out = {}
    try:
        r = requests.get("https://finans.truncgil.com/today.json", timeout=8)
        data = r.json()
        mapping = {"USDTRY": "ABD DOLARI", "EURTRY": "EURO", "GBPTRY": "İNGİLİZ STERLİNİ", "GRAM_ALTIN": "Gram Altın"}
        for sym, key in mapping.items():
            item = data.get(key) or {}
            val = item.get("Satış") or item.get("Alış")
            if val:
                out[sym] = float(str(val).replace(".", "").replace(",", "."))
    except Exception:
        pass
    return out


def get_stooq_price(symbol: str, usd_try: float | None = None) -> float | None:
    # Free CSV endpoint. Works for some US symbols; BIST coverage may vary.
    candidates = []
    s = symbol.upper().strip()
    if s.endswith(".US"):
        candidates.append(s.replace(".US", ".US").lower())
        candidates.append(s.replace(".US", "").lower() + ".us")
    elif s in ["RKLB", "SPCX"]:
        candidates.append(s.lower() + ".us")
    else:
        candidates.append(s.lower() + ".tr")
        candidates.append(s.lower() + ".is")
    for c in candidates:
        try:
            url = f"https://stooq.com/q/l/?s={c}&f=sd2t2ohlcv&h&e=csv"
            txt = requests.get(url, timeout=8).text
            row = pd.read_csv(io.StringIO(txt)).iloc[0]
            close = row.get("Close")
            if close is not None and str(close) != "N/D":
                price = float(close)
                if c.endswith(".us") and usd_try:
                    return price * usd_try
                return price
        except Exception:
            continue
    return None


def price_assets(df: pd.DataFrame) -> pd.DataFrame:
    rates = get_truncgil_rates()
    usd_try = rates.get("USDTRY") or None
    rows = []
    for _, r in df.iterrows():
        price = None
        note = ""
        sym = str(r["symbol"]).upper().strip()
        manual = float(r.get("manual_price_try", 0) or 0)
        if sym in rates:
            price = rates[sym]; note = "Online"
        elif r["category"] in ["ABD Hisse", "BIST"]:
            price = get_stooq_price(sym, usd_try=usd_try)
            note = "Online" if price else "Online fiyat alınamadı"
        if not price and manual > 0:
            price = manual; note = "Manuel"
        total = float(r["quantity"]) * price if price else 0
        cost_total = float(r["quantity"]) * float(r.get("cost_try", 0) or 0)
        pnl = total - cost_total if cost_total > 0 else 0
        rows.append({**r.to_dict(), "price_try": price or 0, "total_try": total, "pnl_try": pnl, "source": note or "Fiyat yok"})
    return pd.DataFrame(rows)


def format_try(x: float) -> str:
    return f"{x:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def snapshot_total(total: float) -> None:
    con = db(); cur = con.cursor()
    cur.execute("INSERT INTO snapshots(ts,total_try) VALUES(?,?)", (datetime.now().isoformat(timespec="seconds"), float(total)))
    con.commit(); con.close()


def load_snapshots() -> pd.DataFrame:
    con = db(); df = pd.read_sql_query("SELECT * FROM snapshots ORDER BY ts", con); con.close(); return df


def add_transaction(asset: str, action: str, quantity: float, price_try: float, note: str) -> None:
    con = db(); cur = con.cursor()
    cur.execute("INSERT INTO transactions(date,asset,action,quantity,price_try,note) VALUES(?,?,?,?,?,?)", (date.today().isoformat(), asset, action, quantity, price_try, note))
    # Apply to asset quantity for buy/sell
    if action in ["Alış", "Satış"]:
        sign = 1 if action == "Alış" else -1
        cur.execute("UPDATE assets SET quantity = quantity + ? WHERE name = ? OR symbol = ?", (sign * quantity, asset, asset))
    con.commit(); con.close()


def load_transactions() -> pd.DataFrame:
    con = db(); df = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", con); con.close(); return df


init_db()
assets = load_assets()
priced = price_assets(assets)
total = float(priced["total_try"].sum()) if not priced.empty else 0

st.title("💼 Benim Finans")
st.caption("Kişisel yatırım takip paneli. Yatırım tavsiyesi değildir.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Portföy", format_try(total))
by_cat = priced.groupby("category", as_index=False)["total_try"].sum() if not priced.empty else pd.DataFrame()
col2.metric("Varlık Sayısı", len(priced))
col3.metric("En Büyük Kategori", by_cat.sort_values("total_try", ascending=False).iloc[0]["category"] if not by_cat.empty and by_cat["total_try"].sum() > 0 else "-")
col4.metric("Son Güncelleme", datetime.now().strftime("%H:%M"))

if st.button("💾 Bugünkü değeri kaydet", use_container_width=True):
    snapshot_total(total)
    st.success("Bugünkü portföy değeri kaydedildi.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏠 Ana Sayfa", "💰 Portföy", "➕ Varlık Ekle", "🧾 İşlemler", "📈 Grafikler", "📄 Raporlar"])

with tab1:
    c1, c2 = st.columns([1,1])
    with c1:
        st.subheader("Kategori özeti")
        if not by_cat.empty and by_cat["total_try"].sum() > 0:
            by_cat["Toplam"] = by_cat["total_try"].apply(format_try)
            st.dataframe(by_cat[["category", "Toplam"]].rename(columns={"category":"Kategori"}), use_container_width=True, hide_index=True)
        else:
            st.info("Fiyat verileri geldikçe kategori özeti oluşacak.")
    with c2:
        st.subheader("Portföy dağılımı")
        if not by_cat.empty and by_cat["total_try"].sum() > 0:
            fig = px.pie(by_cat, values="total_try", names="category", hole=.45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Dağılım grafiği için fiyat bilgisi gerekli.")

with tab2:
    st.subheader("Portföy düzenle")
    edit = priced[["id","name","symbol","category","quantity","cost_try","manual_price_try","price_try","total_try","source"]].copy()
    edit = edit.rename(columns={"name":"Varlık","symbol":"Sembol","category":"Kategori","quantity":"Adet/Gram","cost_try":"Alış Maliyeti TL","manual_price_try":"Manuel Fiyat TL","price_try":"Güncel Fiyat TL","total_try":"Toplam TL","source":"Kaynak"})
    st.caption("Adet, kategori, alış maliyeti ve manuel fiyatı burada değiştirebilirsin. Online fiyat gelmezse manuel fiyat kullanılır.")
    edited = st.data_editor(edit, use_container_width=True, num_rows="dynamic", key="asset_editor", disabled=["Güncel Fiyat TL","Toplam TL","Kaynak"])
    if st.button("Portföy değişikliklerini kaydet", type="primary"):
        save = edited.rename(columns={"Varlık":"name","Sembol":"symbol","Kategori":"category","Adet/Gram":"quantity","Alış Maliyeti TL":"cost_try","Manuel Fiyat TL":"manual_price_try"})
        keep = ["id","name","symbol","category","quantity","cost_try","manual_price_try"]
        old = load_assets()[["id","created_at"]]
        save = save[keep].merge(old, on="id", how="left")
        save_assets(save)
        st.success("Portföy kaydedildi. Sayfayı yenileyebilirsin.")
        st.rerun()

with tab3:
    st.subheader("Yeni varlık ekle")
    with st.form("new_asset"):
        name = st.text_input("Varlık adı", placeholder="Örn: Euro, Akbank, Apple")
        symbol = st.text_input("Sembol", placeholder="Örn: EURTRY, AKBNK, AAPL.US")
        category = st.selectbox("Kategori", CATEGORY_OPTIONS)
        quantity = st.number_input("Adet/Gram", min_value=0.0, step=0.01, format="%.8f")
        cost_try = st.number_input("Alış maliyeti TL", min_value=0.0, step=0.01)
        manual_price = st.number_input("Manuel fiyat TL", min_value=0.0, step=0.01)
        ok = st.form_submit_button("Varlığı ekle")
    if ok and name and symbol:
        con = db(); cur = con.cursor()
        cur.execute("INSERT INTO assets(name,symbol,category,quantity,cost_try,manual_price_try,created_at) VALUES(?,?,?,?,?,?,?)", (name, symbol.upper(), category, quantity, cost_try, manual_price, datetime.now().isoformat(timespec="seconds")))
        con.commit(); con.close()
        st.success("Yeni varlık eklendi.")
        st.rerun()

with tab4:
    st.subheader("İşlem geçmişi")
    asset_names = list(load_assets()["name"]) + list(load_assets()["symbol"])
    with st.form("tx"):
        asset = st.selectbox("Varlık", asset_names)
        action = st.selectbox("İşlem", ["Alış", "Satış", "Temettü", "Komisyon", "Not"])
        qty = st.number_input("Miktar", min_value=0.0, step=0.01, format="%.8f")
        p = st.number_input("Fiyat TL", min_value=0.0, step=0.01)
        note = st.text_input("Not")
        submitted = st.form_submit_button("İşlemi kaydet")
    if submitted:
        add_transaction(asset, action, qty, p, note)
        st.success("İşlem kaydedildi.")
        st.rerun()
    tx = load_transactions()
    st.dataframe(tx, use_container_width=True, hide_index=True)

with tab5:
    st.subheader("Portföy geçmişi")
    hist = load_snapshots()
    if not hist.empty:
        hist["ts"] = pd.to_datetime(hist["ts"])
        fig = px.line(hist, x="ts", y="total_try", markers=True, labels={"ts":"Tarih", "total_try":"Toplam TL"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Grafik için önce 'Bugünkü değeri kaydet' butonuna bas.")

with tab6:
    st.subheader("Raporlar")
    export_df = priced.copy()
    export_df["price_try"] = export_df["price_try"].round(2)
    export_df["total_try"] = export_df["total_try"].round(2)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Portfoy", index=False)
        load_transactions().to_excel(writer, sheet_name="Islemler", index=False)
        load_snapshots().to_excel(writer, sheet_name="Gecmis", index=False)
    st.download_button("📥 Excel indir", data=buf.getvalue(), file_name="benimfinans_rapor.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("PDF raporu V3.1'de daha şık tasarımla eklenecek.")

st.divider()
st.caption("V3.0 • Mobil uyumlu kişisel portföy paneli • Online fiyat alınamazsa manuel fiyat kullanılır.")
