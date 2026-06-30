from __future__ import annotations

import io, json, csv
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

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

st.set_page_config(page_title='Benim Finans V3.4', page_icon='💼', layout='wide')

st.markdown('''
<style>
[data-testid="stSidebar"] {background:#0f172a; color:white;}
[data-testid="stSidebar"] * {color:white;}
.block-container {padding-top: 2rem; max-width: 1180px;}
.big-title {font-size:44px; font-weight:800; margin-bottom:0;}
.subtle {color:#6b7280; font-size:14px;}
.card {border:1px solid #e5e7eb; border-radius:16px; padding:18px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.04)}
.good {color:#059669; font-weight:700}.bad {color:#dc2626; font-weight:700}
.small-muted {color:#6b7280;font-size:13px;}
</style>
''', unsafe_allow_html=True)

CATEGORIES = ['Altın','Döviz','BIST','ABD Hisse','Kripto','Fon','BES','Diğer']
ACTIONS = ['Alış','Satış','Temettü','Komisyon','Nakit','Transfer']


def tr_money(x):
    try:
        return f"{float(x):,.2f} TL".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return '-'


def tr_pct(x):
    try:
        return f"{float(x):+.2f}%".replace('.', ',')
    except Exception:
        return '-'


def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_CSV.exists():
        pd.DataFrame(columns=['asset','symbol','category','quantity','cost_try','manual_price_try']).to_csv(PORTFOLIO_CSV, index=False)
    df = pd.read_csv(PORTFOLIO_CSV)
    for c in ['asset','symbol','category','quantity','cost_try','manual_price_try']:
        if c not in df.columns:
            df[c] = 0.0 if c in ['quantity','cost_try','manual_price_try'] else ''
    for c in ['quantity','cost_try','manual_price_try']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    for c in ['asset','symbol','category']:
        df[c] = df[c].fillna('').astype(str)
    return df[['asset','symbol','category','quantity','cost_try','manual_price_try']]


def save_portfolio(df: pd.DataFrame):
    cols = ['asset','symbol','category','quantity','cost_try','manual_price_try']
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = 0.0 if c in ['quantity','cost_try','manual_price_try'] else ''
    out[cols].to_csv(PORTFOLIO_CSV, index=False)


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
    try:
        r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=8)
        data = r.json()
        val = data.get('rates', {}).get('TRY')
        if val:
            return float(val), 'open.er-api.com'
    except Exception:
        pass
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
    symbol = symbol.upper().replace('=X','').replace('TRY','')
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
        if base in {'EUR','GBP'}:
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
    try:
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
    try:
        sym = symbol.lower()
        url = f'https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv'
        r = requests.get(url, timeout=10, headers={'User-Agent':'Mozilla/5.0'})
        rows = list(csv.DictReader(io.StringIO(r.text)))
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
    if '.' not in ticker and '=' not in ticker:
        p, src = stooq_price(ticker + '.us')
        if p:
            return p, src
    return None, 'Online fiyat yok'


def get_gold_try() -> tuple[float|None,str]:
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
                if float(row.get('manual_price_try',0)) > 0:
                    price, source = float(row['manual_price_try']), 'Manuel fiyat'
                else:
                    price, source = (float(price) if price else 0.0), src
        elif float(row.get('manual_price_try',0)) > 0 and float(price or 0) == 0:
            price, source = float(row['manual_price_try']), 'Manuel fiyat'
        r = row.to_dict()
        r['current_price_try'] = float(price or 0)
        r['total_try'] = r['current_price_try'] * float(row['quantity'])
        r['cost_basis_try'] = float(row.get('cost_try',0)) * float(row['quantity'])
        r['pnl_try'] = r['total_try'] - r['cost_basis_try'] if float(row.get('cost_try',0)) else 0
        r['pnl_pct'] = (r['pnl_try'] / r['cost_basis_try'] * 100) if r['cost_basis_try'] else 0
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
    cols = ['date','datetime','asset','action','quantity','price_try','note']
    if TRANSACTIONS_CSV.exists():
        tx = pd.read_csv(TRANSACTIONS_CSV)
    else:
        tx = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in tx.columns:
            if c == 'date' and 'datetime' in tx.columns:
                tx[c] = pd.to_datetime(tx['datetime'], errors='coerce').dt.date.astype(str)
            elif c == 'datetime':
                tx[c] = datetime.now().isoformat(timespec='seconds')
            else:
                tx[c] = ''
    tx['quantity'] = pd.to_numeric(tx['quantity'], errors='coerce').fillna(0.0)
    tx['price_try'] = pd.to_numeric(tx['price_try'], errors='coerce').fillna(0.0)
    tx['date'] = pd.to_datetime(tx['date'], errors='coerce').dt.date.astype(str)
    tx.loc[tx['date'].isin(['NaT','NaN','None','']), 'date'] = pd.to_datetime(tx['datetime'], errors='coerce').dt.date.astype(str)
    return tx[cols]


def save_transactions(tx: pd.DataFrame):
    tx.to_csv(TRANSACTIONS_CSV, index=False)


def add_transaction(tx_date: date, asset, action, qty, price, note):
    tx = load_transactions()
    new = pd.DataFrame([{
        'date': tx_date.isoformat(),
        'datetime': datetime.now().isoformat(timespec='seconds'),
        'asset': asset,
        'action': action,
        'quantity': qty,
        'price_try': price,
        'note': note
    }])
    tx = pd.concat([tx,new], ignore_index=True)
    save_transactions(tx)


def apply_transaction_to_portfolio(pdf: pd.DataFrame, asset: str, action: str, qty: float, price: float) -> pd.DataFrame:
    idx = pdf.index[pdf['asset']==asset]
    if not len(idx):
        return pdf
    i = idx[0]
    old_qty = float(pdf.loc[i,'quantity'])
    old_cost = float(pdf.loc[i,'cost_try'])
    if action == 'Alış':
        new_qty = old_qty + qty
        if price > 0 and new_qty > 0:
            pdf.loc[i,'cost_try'] = ((old_qty * old_cost) + (qty * price)) / new_qty
        pdf.loc[i,'quantity'] = new_qty
    elif action == 'Satış':
        pdf.loc[i,'quantity'] = max(0, old_qty - qty)
    return pdf


def range_pnl(transactions: pd.DataFrame, enriched: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()
    tx = transactions.copy()
    tx['date_dt'] = pd.to_datetime(tx['date'], errors='coerce').dt.date
    tx = tx[(tx['date_dt'] >= start) & (tx['date_dt'] <= end)]
    if tx.empty:
        return pd.DataFrame()
    prices = enriched.set_index('asset')['current_price_try'].to_dict()
    cats = enriched.set_index('asset')['category'].to_dict()
    rows=[]
    for asset, sub in tx.groupby('asset'):
        buy = sub[sub.action=='Alış']
        sell = sub[sub.action=='Satış']
        div = sub[sub.action=='Temettü']
        com = sub[sub.action=='Komisyon']
        buy_qty = float(buy.quantity.sum())
        sell_qty = float(sell.quantity.sum())
        buy_cost = float((buy.quantity * buy.price_try).sum())
        sell_revenue = float((sell.quantity * sell.price_try).sum())
        dividends = float((div.quantity * div.price_try).sum()) if not div.empty else 0.0
        commissions = float((com.quantity * com.price_try).sum()) if not com.empty else 0.0
        net_qty = max(0.0, buy_qty - sell_qty)
        current_price = float(prices.get(asset, 0) or 0)
        current_value = net_qty * current_price
        pnl = sell_revenue + current_value + dividends - commissions - buy_cost
        rows.append({
            'Varlık': asset,
            'Kategori': cats.get(asset, '-'),
            'Alış Miktarı': buy_qty,
            'Satış Miktarı': sell_qty,
            'Net Miktar': net_qty,
            'Alış Tutarı': buy_cost,
            'Satış Tutarı': sell_revenue,
            'Bugünkü Değer': current_value,
            'Temettü': dividends,
            'Komisyon': commissions,
            'K/Z TL': pnl,
            'K/Z %': (pnl / buy_cost * 100) if buy_cost else 0.0,
        })
    return pd.DataFrame(rows)


def format_report_df(d: pd.DataFrame) -> pd.DataFrame:
    out = d.copy()
    for c in ['Güncel Fiyat TL','Toplam TL','Maliyet TL','K/Z TL','Alış Tutarı','Satış Tutarı','Bugünkü Değer','Temettü','Komisyon']:
        if c in out.columns:
            out[c] = out[c].map(tr_money)
    if 'K/Z %' in out.columns:
        out['K/Z %'] = out['K/Z %'].map(tr_pct)
    return out

with st.sidebar:
    st.title('💼 Benim Finans')
    st.caption('Kişisel portföy sistemi')
    page = st.radio('Menü', ['🏠 Dashboard','💰 Portföy','➕ Varlık Ekle','🧾 İşlemler','📊 Kâr/Zarar','📈 Grafikler','🔔 Alarm','📄 Raporlar','⚙️ Ayarlar'], label_visibility='collapsed')
    st.divider()
    sidebar_refresh = st.button('🔄 Canlı fiyatları yenile', use_container_width=True)

st.markdown('<div class="big-title">💼 Benim Finans</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle">V3.4 • Geçmiş tarihli alımlar, ağırlıklı maliyet, kategori/toplam kâr-zarar ve tarih aralığı analizi • Yatırım tavsiyesi değildir.</div>', unsafe_allow_html=True)

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
cost_total = float(df['cost_basis_try'].sum()) if 'cost_basis_try' in df else 0.0
pnl_total = total - cost_total if cost_total else float(df['pnl_try'].sum()) if 'pnl_try' in df else 0.0
pnl_pct_total = pnl_total / cost_total * 100 if cost_total else 0.0
bigcat = '-'
if total > 0 and not df.empty:
    cat_sum = df.groupby('category')['total_try'].sum().sort_values(ascending=False)
    bigcat = cat_sum.index[0] if len(cat_sum) else '-'

m1,m2,m3,m4 = st.columns(4)
m1.metric('Toplam Portföy', tr_money(total))
m2.metric('Toplam K/Z', tr_money(pnl_total), tr_pct(pnl_pct_total) if cost_total else None)
m3.metric('En Büyük Kategori', bigcat)
m4.metric('Son Güncelleme', datetime.now().strftime('%H:%M'))
st.divider()

if page == '🏠 Dashboard':
    st.subheader('🏠 Dashboard')
    cat = df.groupby('category', as_index=False).agg(total_try=('total_try','sum'), cost_basis_try=('cost_basis_try','sum'), pnl_try=('pnl_try','sum'))
    cat['pnl_pct'] = cat.apply(lambda r: (r.pnl_try/r.cost_basis_try*100) if r.cost_basis_try else 0, axis=1)
    c1,c2 = st.columns([1,1])
    with c1:
        st.markdown('### Kategori Kartları')
        for _, r in cat.iterrows():
            cls = 'good' if r['pnl_try'] >= 0 else 'bad'
            st.markdown(f"<div class='card'><b>{r['category']}</b><br><span style='font-size:24px'>{tr_money(r['total_try'])}</span><br><span class='{cls}'>K/Z {tr_money(r['pnl_try'])} ({tr_pct(r['pnl_pct'])})</span></div><br>", unsafe_allow_html=True)
    with c2:
        if cat['total_try'].sum() > 0:
            fig = px.pie(cat, names='category', values='total_try', hole=.45, title='Portföy dağılımı')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('Grafik için fiyatların gelmesi veya manuel fiyat girilmesi gerekir.')
    st.markdown('### Varlıklar')
    view = df[['asset','category','quantity','current_price_try','total_try','cost_basis_try','pnl_try','pnl_pct','source']].rename(columns={
        'asset':'Varlık','category':'Kategori','quantity':'Miktar','current_price_try':'Güncel Fiyat TL','total_try':'Toplam TL','cost_basis_try':'Maliyet TL','pnl_try':'K/Z TL','pnl_pct':'K/Z %','source':'Kaynak'
    })
    st.dataframe(format_report_df(view), use_container_width=True)

elif page == '💰 Portföy':
    st.subheader('💰 Portföy')
    st.caption('Miktar, kategori, ağırlıklı alış maliyeti ve manuel fiyatı değiştirip kaydedebilirsin.')
    edit = df[['asset','symbol','category','quantity','cost_try','manual_price_try']].copy()
    edited = st.data_editor(edit, num_rows='dynamic', use_container_width=True, key='portfolio_editor')
    c1,c2 = st.columns([2,1])
    with c1:
        if st.button('💾 Portföy değişikliklerini kaydet', use_container_width=True):
            edited = edited.dropna(subset=['asset','symbol'])
            save_portfolio(edited)
            st.success('Portföy kaydedildi.')
            st.rerun()
    with c2:
        del_asset = st.selectbox('Silinecek varlık', ['-'] + df['asset'].tolist())
        if st.button('🗑️ Varlık sil', use_container_width=True) and del_asset != '-':
            save_portfolio(base_df[base_df['asset'] != del_asset])
            st.success(f'{del_asset} silindi.')
            st.rerun()
    st.markdown('### Kategorilere göre görünüm')
    for cat, sub in df.groupby('category'):
        with st.expander(f'{cat} — {tr_money(sub.total_try.sum())} • K/Z {tr_money(sub.pnl_try.sum())}'):
            subview = sub[['asset','quantity','current_price_try','total_try','cost_basis_try','pnl_try','pnl_pct','source']].rename(columns={
                'asset':'Varlık','quantity':'Miktar','current_price_try':'Güncel Fiyat TL','total_try':'Toplam TL','cost_basis_try':'Maliyet TL','pnl_try':'K/Z TL','pnl_pct':'K/Z %','source':'Kaynak'
            })
            st.dataframe(format_report_df(subview), use_container_width=True)

elif page == '➕ Varlık Ekle':
    st.subheader('➕ Yeni Varlık Ekle')
    with st.form('add_asset'):
        asset = st.text_input('Varlık adı', placeholder='Örn: Euro, Apple, Tüpraş')
        symbol = st.text_input('Sembol', placeholder='Örn: EURTRY, AAPL.US, TUPRS')
        category = st.selectbox('Kategori', CATEGORIES)
        qty = st.number_input('Mevcut adet / gram / miktar', min_value=0.0, step=0.01, format='%.6f')
        cost = st.number_input('Ağırlıklı alış maliyeti TL', min_value=0.0, step=0.01)
        manual = st.number_input('Manuel fiyat TL', min_value=0.0, step=0.01)
        submitted = st.form_submit_button('➕ Varlığı ekle')
        if submitted and asset and symbol:
            new = pd.DataFrame([{'asset':asset,'symbol':symbol,'category':category,'quantity':qty,'cost_try':cost,'manual_price_try':manual}])
            save_portfolio(pd.concat([base_df,new], ignore_index=True))
            st.success(f'{asset} eklendi.')
            st.rerun()

elif page == '🧾 İşlemler':
    st.subheader('🧾 İşlemler')
    st.caption('Geçmiş tarihli alım/satım girebilirsin. Alış işlemleri ağırlıklı maliyeti otomatik günceller.')
    with st.form('tx'):
        tx_date = st.date_input('İşlem tarihi', value=date.today())
        asset = st.selectbox('Varlık', df['asset'].tolist())
        action = st.selectbox('İşlem', ACTIONS)
        qty = st.number_input('Miktar', min_value=0.0, step=0.01, format='%.6f')
        price = st.number_input('Birim fiyat TL', min_value=0.0, step=0.01)
        note = st.text_input('Not')
        if st.form_submit_button('İşlemi kaydet ve portföye yansıt'):
            add_transaction(tx_date, asset, action, qty, price, note)
            pdf = apply_transaction_to_portfolio(base_df.copy(), asset, action, qty, price)
            save_portfolio(pdf)
            st.success('İşlem kaydedildi ve portföye işlendi.')
            st.rerun()
    st.markdown('### İşlem geçmişi')
    tx = load_transactions().sort_values(['date','datetime'], ascending=False)
    edited_tx = st.data_editor(tx, use_container_width=True, num_rows='dynamic', key='tx_editor')
    if st.button('💾 İşlem geçmişini kaydet', use_container_width=True):
        save_transactions(edited_tx)
        st.success('İşlem geçmişi kaydedildi. Not: Portföy miktarını yeniden hesaplamak için ilgili işlemleri tekrar kontrol et.')
        st.rerun()

elif page == '📊 Kâr/Zarar':
    st.subheader('📊 Kâr/Zarar Analizi')
    st.markdown('### Tüm portföy bazında')
    all_view = df[['asset','category','quantity','current_price_try','total_try','cost_basis_try','pnl_try','pnl_pct']].rename(columns={
        'asset':'Varlık','category':'Kategori','quantity':'Miktar','current_price_try':'Güncel Fiyat TL','total_try':'Toplam TL','cost_basis_try':'Maliyet TL','pnl_try':'K/Z TL','pnl_pct':'K/Z %'
    })
    st.dataframe(format_report_df(all_view), use_container_width=True)

    st.markdown('### Kategori bazında')
    catp = df.groupby('category', as_index=False).agg(**{'Toplam TL':('total_try','sum'), 'Maliyet TL':('cost_basis_try','sum'), 'K/Z TL':('pnl_try','sum')})
    catp['K/Z %'] = catp.apply(lambda r: r['K/Z TL']/r['Maliyet TL']*100 if r['Maliyet TL'] else 0, axis=1)
    catp = catp.rename(columns={'category':'Kategori'})
    st.dataframe(format_report_df(catp), use_container_width=True)

    st.markdown('### Seçilen tarih aralığına göre')
    st.caption('Bu bölüm, seçilen aralıkta girilen işlemlerin bugünkü fiyatlara göre yaklaşık K/Z hesabını gösterir.')
    tx = load_transactions()
    default_start = date.today().replace(day=1)
    c1,c2 = st.columns(2)
    start = c1.date_input('Başlangıç', value=default_start, key='pnl_start')
    end = c2.date_input('Bitiş', value=date.today(), key='pnl_end')
    rp = range_pnl(tx, df, start, end)
    if rp.empty:
        st.info('Bu tarih aralığında işlem bulunamadı.')
    else:
        t1,t2,t3 = st.columns(3)
        t1.metric('Aralık Alış Tutarı', tr_money(rp['Alış Tutarı'].sum()))
        t2.metric('Aralık Bugünkü/Realize Değer', tr_money(rp['Bugünkü Değer'].sum() + rp['Satış Tutarı'].sum()))
        t3.metric('Aralık K/Z', tr_money(rp['K/Z TL'].sum()), tr_pct(rp['K/Z TL'].sum()/rp['Alış Tutarı'].sum()*100) if rp['Alış Tutarı'].sum() else None)
        st.dataframe(format_report_df(rp), use_container_width=True)
        cat_rp = rp.groupby('Kategori', as_index=False).agg(**{'Alış Tutarı':('Alış Tutarı','sum'), 'Bugünkü Değer':('Bugünkü Değer','sum'), 'Satış Tutarı':('Satış Tutarı','sum'), 'K/Z TL':('K/Z TL','sum')})
        cat_rp['K/Z %'] = cat_rp.apply(lambda r: r['K/Z TL']/r['Alış Tutarı']*100 if r['Alış Tutarı'] else 0, axis=1)
        st.markdown('#### Kategori özeti')
        st.dataframe(format_report_df(cat_rp), use_container_width=True)

elif page == '📈 Grafikler':
    st.subheader('📈 Grafikler')
    if HISTORY_CSV.exists():
        h = pd.read_csv(HISTORY_CSV)
        fig = px.line(h, x='datetime', y='total_try', title='Portföy geçmişi')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('Bugünkü değeri kaydet butonuna bastıkça grafik oluşur.')
    if not df.empty and df['pnl_try'].abs().sum() > 0:
        fig2 = px.bar(df, x='asset', y='pnl_try', color='category', title='Varlık bazında K/Z')
        st.plotly_chart(fig2, use_container_width=True)

elif page == '🔔 Alarm':
    st.subheader('🔔 Alarm')
    st.info('Hedef fiyatları şimdilik not olarak tutabilirsin. Bildirim sistemi sonraki sürümde eklenecek.')
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
