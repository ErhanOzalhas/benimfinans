from __future__ import annotations

import io, os, json, sqlite3, time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import plotly.express as px

DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_CSV = Path('portfolio.csv')
CACHE_FILE = DATA_DIR / 'price_cache.json'
HISTORY_CSV = DATA_DIR / 'history.csv'
TRANSACTIONS_CSV = DATA_DIR / 'transactions.csv'

st.set_page_config(page_title='Benim Finans V3.3', page_icon='💼', layout='wide')

st.markdown('''
<style>
[data-testid="stSidebar"] {background:#0f172a; color:white;}
[data-testid="stSidebar"] * {color:white;}
.block-container {padding-top: 2rem; max-width: 1180px;}
.big-title {font-size:44px; font-weight:800; margin-bottom:0;}
.subtle {color:#6b7280; font-size:14px;}
.card {border:1px solid #e5e7eb; border-radius:16px; padding:18px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.04)}
.good {color:#059669; font-weight:700}.bad {color:#dc2626; font-weight:700}
</style>
''', unsafe_allow_html=True)


def tr_money(x):
    try:
        return f"{float(x):,.2f} TL".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return '-'


def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_CSV.exists():
        pd.DataFrame(columns=['asset','symbol','category','quantity','cost_try','manual_price_try']).to_csv(PORTFOLIO_CSV, index=False)
    df = pd.read_csv(PORTFOLIO_CSV)
    for c in ['quantity','cost_try','manual_price_try']:
        df[c] = pd.to_numeric(df.get(c,0), errors='coerce').fillna(0.0)
    for c in ['asset','symbol','category']:
        df[c] = df[c].fillna('').astype(str)
    return df


def save_portfolio(df: pd.DataFrame):
    cols = ['asset','symbol','category','quantity','cost_try','manual_price_try']
    df = df[cols].copy()
    df.to_csv(PORTFOLIO_CSV, index=False)


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def get_usdtry() -> tuple[float|None,str]:
    # 1) exchangerate.host-like free endpoint alternative
    try:
        r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=8)
        data = r.json()
        val = data.get('rates', {}).get('TRY')
        if val:
            return float(val), 'open.er-api.com'
    except Exception:
        pass
    # 2) TCMB previous official xml
    try:
        r = requests.get('https://www.tcmb.gov.tr/kurlar/today.xml', timeout=8)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        for cur in root.findall('Currency'):
            if cur.attrib.get('CurrencyCode') == 'USD':
                return float(cur.find('ForexSelling').text.replace(',', '.')), 'TCMB'
    except Exception:
        pass
    return None, 'Fiyat yok'


def get_fx(symbol: str) -> tuple[float|None,str]:
    symbol = symbol.upper().replace('=X','')
    base = symbol[:3] if len(symbol)>=3 else symbol
    if base == 'USD':
        return get_usdtry()
    try:
        r = requests.get(f'https://open.er-api.com/v6/latest/{base}', timeout=8)
        data = r.json()
        val = data.get('rates', {}).get('TRY')
        if val:
            return float(val), 'open.er-api.com'
    except Exception:
        pass
    try:
        code_map = {'EUR':'EUR','GBP':'GBP'}
        if base in code_map:
            r = requests.get('https://www.tcmb.gov.tr/kurlar/today.xml', timeout=8)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            for cur in root.findall('Currency'):
                if cur.attrib.get('CurrencyCode') == base:
                    return float(cur.find('ForexSelling').text.replace(',', '.')), 'TCMB'
    except Exception:
        pass
    return None, 'Fiyat yok'


def yahoo_chart_price(ticker: str) -> tuple[float|None,str]:
    """Yahoo'nun hafif chart endpoint'i. yfinance kullanmaz."""
    try:
        from urllib.parse import quote
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?range=5d&interval=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        result = data.get('chart', {}).get('result') or []
        if result:
            closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
            vals = [x for x in closes if x is not None]
            if vals:
                return float(vals[-1]), 'Yahoo Chart'
    except Exception:
        pass
    return None, 'Yahoo Chart fiyat yok'


def stooq_price(symbol: str) -> tuple[float|None,str]:
    """Stooq CSV yedeği. US hisseleri için rklb.us gibi çalışır."""
    try:
        sym = symbol.lower()
        url = f'https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv'
        r = requests.get(url, timeout=10, headers={'User-Agent':'Mozilla/5.0'})
        import csv, io as _io
        rows = list(csv.DictReader(_io.StringIO(r.text)))
        if rows:
            close = rows[0].get('Close')
            if close and close != 'N/D':
                return float(close), 'Stooq'
    except Exception:
        pass
    return None, 'Stooq fiyat yok'


def online_price(ticker: str) -> tuple[float|None,str]:
    p, src = yahoo_chart_price(ticker)
    if p:
        return p, src
    # US fallback: RKLB -> rklb.us
    if '.' not in ticker and '=' not in ticker:
        p, src = stooq_price(ticker + '.us')
        if p:
            return p, src
    return None, 'Online fiyat yok'

def get_gold_try() -> tuple[float|None,str]:
    # Use XAUUSD * USDTRY / 31.1035 as gram gold proxy
    usdtry, usdsrc = get_usdtry()
    xau, xsrc = online_price('GC=F')
    if xau and usdtry:
        return float(xau) * float(usdtry) / 31.1034768, f'Ons altın + {usdsrc}'
    return None, 'Altın fiyat yok'


def get_price(row) -> tuple[float|None,str]:
    symbol = str(row['symbol']).strip().upper()
    cat = str(row['category']).strip()
    if cat == 'Döviz':
        return get_fx(symbol)
    if cat == 'Altın' or symbol == 'GRAM_ALTIN':
        return get_gold_try()
    if cat == 'BIST':
        p, src = online_price(symbol + '.IS')
        if p: return p, 'Yahoo BIST'
        return None, 'BIST online fiyat alınamadı'
    if cat == 'ABD Hisse':
        t = symbol.replace('.US','')
        p, src = online_price(t)
        if p:
            usd, usrc = get_usdtry()
            if usd: return p*usd, f'Yahoo USD x {usrc}'
            return p, 'Yahoo USD'
        return None, 'ABD hisse fiyat yok'
    p, src = online_price(symbol)
    return p, src


def enrich(df: pd.DataFrame, refresh=False) -> pd.DataFrame:
    cache = load_cache()
    rows=[]
    for _, row in df.iterrows():
        key = str(row['symbol']).upper()
        cached = cache.get(key, {})
        price = cached.get('price')
        source = 'Cache' if price else ''
        if refresh or price is None:
            p, src = get_price(row)
            if p and p > 0:
                price, source = p, src
                cache[key] = {'price': price, 'source': source, 'ts': datetime.now().isoformat()}
            else:
                if row.get('manual_price_try',0) > 0:
                    price, source = float(row['manual_price_try']), 'Manuel fiyat'
                else:
                    price, source = (float(price) if price else 0.0), src
        elif row.get('manual_price_try',0) > 0 and price == 0:
            price, source = float(row['manual_price_try']), 'Manuel fiyat'
        r = row.to_dict()
        r['current_price_try'] = float(price or 0)
        r['total_try'] = r['current_price_try'] * float(row['quantity'])
        r['pnl_try'] = (r['current_price_try'] - float(row.get('cost_try',0))) * float(row['quantity']) if float(row.get('cost_try',0)) else 0
        r['source'] = source or 'Fiyat yok'
        rows.append(r)
    save_cache(cache)
    return pd.DataFrame(rows)


def save_history(total):
    h = pd.DataFrame([{'datetime': datetime.now().isoformat(timespec='seconds'), 'total_try': total}])
    if HISTORY_CSV.exists():
        old = pd.read_csv(HISTORY_CSV)
        h = pd.concat([old,h], ignore_index=True)
    h.to_csv(HISTORY_CSV, index=False)


def load_transactions():
    if TRANSACTIONS_CSV.exists():
        return pd.read_csv(TRANSACTIONS_CSV)
    return pd.DataFrame(columns=['datetime','asset','action','quantity','price_try','note'])


def add_transaction(asset, action, qty, price, note):
    tx = load_transactions()
    tx = pd.concat([tx, pd.DataFrame([{'datetime':datetime.now().isoformat(timespec='seconds'), 'asset':asset, 'action':action, 'quantity':qty, 'price_try':price, 'note':note}])], ignore_index=True)
    tx.to_csv(TRANSACTIONS_CSV, index=False)

with st.sidebar:
    st.title('💼 Benim Finans')
    st.caption('Kişisel portföy sistemi')
    page = st.radio('Menü', ['🏠 Dashboard','💰 Portföy','➕ Varlık Ekle','🧾 İşlemler','📈 Grafikler','🔔 Alarm','📄 Raporlar','⚙️ Ayarlar'], label_visibility='collapsed')
    st.divider()
    sidebar_refresh = st.button('🔄 Canlı fiyatları yenile', use_container_width=True)

st.markdown('<div class="big-title">💼 Benim Finans</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle">V3.3 • Görünür yenileme butonu, canlı fiyat kaynakları ve portföy al/sat işlemleri • Yatırım tavsiyesi değildir.</div>', unsafe_allow_html=True)

base_df = load_portfolio()
colA, colB = st.columns([1,1])
with colA:
    refresh = st.button('🔄 Fiyatları yenile', use_container_width=True, type='primary') or sidebar_refresh
with colB:
    if st.button('💾 Bugünkü değeri kaydet', use_container_width=True):
        tmp = enrich(base_df, refresh=False)
        save_history(tmp['total_try'].sum())
        st.success('Bugünkü değer kaydedildi.')

df = enrich(base_df, refresh=refresh)
if refresh:
    st.toast('Fiyatlar güncellendi / kaynaklar denendi', icon='🔄')
total = float(df['total_try'].sum()) if not df.empty else 0.0
bigcat = '-'
if total > 0 and not df.empty:
    cat_sum = df.groupby('category')['total_try'].sum().sort_values(ascending=False)
    bigcat = cat_sum.index[0] if len(cat_sum) else '-'

m1,m2,m3,m4 = st.columns(4)
m1.metric('Toplam Portföy', tr_money(total))
m2.metric('Varlık Sayısı', len(df))
m3.metric('En Büyük Kategori', bigcat)
m4.metric('Son Güncelleme', datetime.now().strftime('%H:%M'))
st.divider()

if page == '🏠 Dashboard':
    st.subheader('🏠 Dashboard')
    cat = df.groupby('category', as_index=False)['total_try'].sum()
    c1,c2 = st.columns([1,1])
    with c1:
        st.markdown('### Kategori Kartları')
        for _, r in cat.iterrows():
            st.markdown(f"<div class='card'><b>{r['category']}</b><br><span style='font-size:24px'>{tr_money(r['total_try'])}</span></div><br>", unsafe_allow_html=True)
    with c2:
        if cat['total_try'].sum() > 0:
            fig = px.pie(cat, names='category', values='total_try', hole=.45, title='Portföy dağılımı')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('Grafik için fiyatların gelmesi veya manuel fiyat girilmesi gerekir.')
    st.markdown('### Varlıklar')
    st.dataframe(df[['asset','category','quantity','current_price_try','total_try','source']], use_container_width=True)

elif page == '💰 Portföy':
    st.subheader('💰 Portföy')
    st.caption('Miktar, kategori, alış maliyeti ve manuel fiyatı değiştirip kaydedebilirsin.')
    edit = df[['asset','symbol','category','quantity','cost_try','manual_price_try']].copy()
    edited = st.data_editor(edit, num_rows='dynamic', use_container_width=True, key='portfolio_editor')
    c1,c2 = st.columns([2,1])
    with c1:
        if st.button('💾 Portföy değişikliklerini kaydet', use_container_width=True):
            edited = edited.dropna(subset=['asset','symbol'])
            save_portfolio(edited.rename(columns={}))
            st.success('Portföy kaydedildi. Sayfayı yenileyebilirsin.')
            st.rerun()
    with c2:
        del_asset = st.selectbox('Silinecek varlık', ['-'] + df['asset'].tolist())
        if st.button('🗑️ Varlık sil', use_container_width=True) and del_asset != '-':
            save_portfolio(base_df[base_df['asset'] != del_asset])
            st.success(f'{del_asset} silindi.')
            st.rerun()
    st.markdown('### Kategorilere göre görünüm')
    for cat, sub in df.groupby('category'):
        with st.expander(f'{cat} — {tr_money(sub.total_try.sum())}'):
            st.dataframe(sub[['asset','quantity','current_price_try','total_try','source']], use_container_width=True)

elif page == '➕ Varlık Ekle':
    st.subheader('➕ Yeni Varlık Ekle')
    with st.form('add_asset'):
        asset = st.text_input('Varlık adı', placeholder='Örn: Euro, Apple, Tüpraş')
        symbol = st.text_input('Sembol', placeholder='Örn: EURTRY, AAPL.US, TUPRS')
        category = st.selectbox('Kategori', ['Altın','Döviz','BIST','ABD Hisse','Kripto','Fon','BES','Diğer'])
        qty = st.number_input('Adet / Gram / Miktar', min_value=0.0, step=0.01, format='%.6f')
        cost = st.number_input('Alış maliyeti TL', min_value=0.0, step=0.01)
        manual = st.number_input('Manuel fiyat TL', min_value=0.0, step=0.01)
        submitted = st.form_submit_button('➕ Varlığı ekle')
        if submitted and asset and symbol:
            new = pd.DataFrame([{'asset':asset,'symbol':symbol,'category':category,'quantity':qty,'cost_try':cost,'manual_price_try':manual}])
            save_portfolio(pd.concat([base_df,new], ignore_index=True))
            st.success(f'{asset} eklendi.')
            st.rerun()

elif page == '🧾 İşlemler':
    st.subheader('🧾 İşlemler')
    with st.form('tx'):
        asset = st.selectbox('Varlık', df['asset'].tolist())
        action = st.selectbox('İşlem', ['Alış','Satış','Temettü','Komisyon'])
        qty = st.number_input('Miktar', min_value=0.0, step=0.01, format='%.6f')
        price = st.number_input('Fiyat TL', min_value=0.0, step=0.01)
        note = st.text_input('Not')
        if st.form_submit_button('İşlemi kaydet ve portföye yansıt'):
            add_transaction(asset, action, qty, price, note)
            pdf = base_df.copy()
            idx = pdf.index[pdf['asset']==asset]
            if len(idx):
                i = idx[0]
                if action == 'Alış': pdf.loc[i,'quantity'] += qty
                elif action == 'Satış': pdf.loc[i,'quantity'] = max(0, pdf.loc[i,'quantity'] - qty)
                if price > 0 and action in ['Alış','Satış']:
                    pdf.loc[i,'cost_try'] = price
                save_portfolio(pdf)
            st.success('İşlem kaydedildi.')
            st.rerun()
    st.dataframe(load_transactions(), use_container_width=True)

elif page == '📈 Grafikler':
    st.subheader('📈 Grafikler')
    if HISTORY_CSV.exists():
        h = pd.read_csv(HISTORY_CSV)
        fig = px.line(h, x='datetime', y='total_try', title='Portföy geçmişi')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('Bugünkü değeri kaydet butonuna bastıkça grafik oluşur.')

elif page == '🔔 Alarm':
    st.subheader('🔔 Alarm')
    st.info('V3.3 sürümünde e-posta/Telegram bildirimleri eklenecek. Şimdilik hedef fiyatlarını not olarak tutabilirsin.')
    st.data_editor(pd.DataFrame(columns=['Varlık','Hedef fiyat TL','Yön','Not']), num_rows='dynamic', use_container_width=True)

elif page == '📄 Raporlar':
    st.subheader('📄 Raporlar')
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Portfoy')
        load_transactions().to_excel(writer, index=False, sheet_name='Islemler')
    st.download_button('📥 Excel indir', data=out.getvalue(), file_name='benim_finans_rapor.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

elif page == '⚙️ Ayarlar':
    st.subheader('⚙️ Ayarlar')
    st.write('Veri dosyaları:')
    st.code(f'{PORTFOLIO_CSV}\n{CACHE_FILE}\n{HISTORY_CSV}\n{TRANSACTIONS_CSV}')
    if st.button('🧹 Fiyat cache temizle'):
        if CACHE_FILE.exists(): CACHE_FILE.unlink()
        st.success('Cache temizlendi.')
