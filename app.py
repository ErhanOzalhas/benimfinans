import io, json, os, time
from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, 'data')
os.makedirs(DATA, exist_ok=True)
PORTFOLIO = os.path.join(BASE, 'portfolio.csv')
MANUAL = os.path.join(DATA, 'manual_prices.csv')
HISTORY = os.path.join(DATA, 'history.csv')
TX = os.path.join(DATA, 'transactions.csv')
CACHE = os.path.join(DATA, 'price_cache.json')

st.set_page_config(page_title='Kişisel Yatırım Paneli V2.3', page_icon='📊', layout='wide')
st.markdown('''
<style>
.big {font-size:42px;font-weight:800;margin-bottom:0}.sub {color:#6b7280;font-size:14px}.small {font-size:13px;color:#6b7280}
</style>
''', unsafe_allow_html=True)

TYPE_LABELS = {'gold':'Altın','fx':'Döviz','bist_stock':'BIST Hisse','us_stock':'ABD Hisse','other':'Diğer'}
TYPE_OPTIONS = list(TYPE_LABELS.keys())


def money(x):
    if x is None or pd.isna(x): return '-'
    return f"{float(x):,.2f} TL".replace(',', 'X').replace('.', ',').replace('X', '.')

def pct(x):
    if x is None or pd.isna(x): return '-'
    return f"{float(x):+.2f}%".replace('.', ',')

def load_cache():
    if os.path.exists(CACHE):
        try: return json.load(open(CACHE))
        except Exception: return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE, 'w'), ensure_ascii=False, indent=2)

def req(url, **kw):
    return requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=8, **kw)

def ensure_files():
    if not os.path.exists(PORTFOLIO):
        pd.DataFrame(columns=['asset','type','symbol','quantity','buy_price_try']).to_csv(PORTFOLIO,index=False)
    if not os.path.exists(MANUAL):
        pd.DataFrame(columns=['symbol','price_try','previous_close_try']).to_csv(MANUAL,index=False)
    for path, cols in [(HISTORY,['timestamp','total_try','daily_change_try','weekly_change_try','monthly_change_try']), (TX,['date','asset','action','quantity','price_try','note'])]:
        if not os.path.exists(path): pd.DataFrame(columns=cols).to_csv(path,index=False)
ensure_files()

def normalize_portfolio(df):
    for c in ['asset','type','symbol','quantity','buy_price_try']:
        if c not in df.columns: df[c] = '' if c in ['asset','type','symbol'] else None
    df = df[['asset','type','symbol','quantity','buy_price_try']].copy()
    df['asset']=df['asset'].fillna('').astype(str)
    df['type']=df['type'].fillna('other').astype(str)
    df['symbol']=df['symbol'].fillna('').astype(str).str.upper().str.strip()
    df['quantity']=pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0)
    df['buy_price_try']=pd.to_numeric(df['buy_price_try'], errors='coerce')
    return df

def load_portfolio(): return normalize_portfolio(pd.read_csv(PORTFOLIO))
def save_portfolio(df): normalize_portfolio(df).to_csv(PORTFOLIO,index=False)

def tcmb_rate(code):
    code = code.upper().replace('TRY','').replace('=X','')
    if code in ['TL','TRY']: return 1.0
    r=req('https://www.tcmb.gov.tr/kurlar/today.xml')
    import xml.etree.ElementTree as ET
    root=ET.fromstring(r.content)
    for cur in root.findall('Currency'):
        if cur.attrib.get('CurrencyCode')==code:
            val=cur.findtext('ForexSelling') or cur.findtext('BanknoteSelling')
            return float(val.replace(',', '.'))
    raise ValueError(f'TCMB {code} bulunamadı')

def stooq_us_price(symbol):
    s=symbol.lower().replace('.us','.us')
    if not s.endswith('.us'): s += '.us'
    url=f'https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv'
    df=pd.read_csv(io.StringIO(req(url).text))
    if df.empty or str(df.loc[0,'Close']).lower()=='nan': raise ValueError('Stooq fiyat yok')
    close=float(df.loc[0,'Close']); openp=float(df.loc[0,'Open']) if not pd.isna(df.loc[0,'Open']) else close
    return close, openp

def yahoo_price(symbol):
    ysym=symbol[:-3] if symbol.upper().endswith('.US') else symbol
    data=req(f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range=5d&interval=1d').json()
    result=data.get('chart',{}).get('result')
    if not result: raise ValueError('Yahoo fiyat yok')
    meta=result[0].get('meta',{})
    price=meta.get('regularMarketPrice') or meta.get('previousClose')
    prev=meta.get('chartPreviousClose') or meta.get('previousClose') or price
    if price is None: raise ValueError('Yahoo fiyat yok')
    return float(price), float(prev)

def bist_try_price(symbol):
    symbol=symbol.upper().replace('.IS','')
    for s in [f'{symbol.lower()}.tr', f'{symbol.lower()}.is']:
        try:
            df=pd.read_csv(io.StringIO(req(f'https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv').text))
            close=float(df.loc[0,'Close']); openp=float(df.loc[0,'Open']) if not pd.isna(df.loc[0,'Open']) else close
            if close>0: return close, openp
        except Exception: pass
    return yahoo_price(symbol + '.IS')

def gold_try_price(usdtry):
    close, openp = yahoo_price('GC=F')
    return close/31.1034768*usdtry, openp/31.1034768*usdtry

def manual_lookup(symbol):
    if not os.path.exists(MANUAL): return None
    m=pd.read_csv(MANUAL)
    if m.empty or 'symbol' not in m.columns: return None
    m['symbol']=m['symbol'].astype(str).str.upper().str.strip()
    row=m[m['symbol']==symbol.upper().strip()]
    if row.empty: return None
    p=pd.to_numeric(row.iloc[0].get('price_try'), errors='coerce')
    pc=pd.to_numeric(row.iloc[0].get('previous_close_try'), errors='coerce')
    if pd.isna(p): return None
    return float(p), None if pd.isna(pc) else float(pc), 'Manuel fiyat'

def get_price(row, cache, force=False):
    symbol=str(row['symbol']).upper().strip(); typ=row['type']
    cached=cache.get(symbol,{})
    if not force and cached.get('ts') and time.time()-cached['ts'] < 900:
        return cached.get('price'), cached.get('prev'), 'Cache'
    manual=manual_lookup(symbol)
    try:
        if typ=='fx':
            code = symbol.replace('TRY','').replace('=X','')
            price=tcmb_rate(code); prev=cached.get('price') or price
        elif typ=='gold':
            price, prev=gold_try_price(tcmb_rate('USD'))
        elif typ=='us_stock':
            usdtry=tcmb_rate('USD')
            try: usd, prev_usd=stooq_us_price(symbol)
            except Exception: usd, prev_usd=yahoo_price(symbol)
            price=usd*usdtry; prev=prev_usd*usdtry
        elif typ=='bist_stock':
            price, prev=bist_try_price(symbol)
        else:
            if not manual: raise ValueError('Bu tür için manuel fiyat gerekli')
            price, prev, msg = manual
            cache[symbol]={'price':price,'prev':prev or price,'ts':time.time()}
            return price, prev or price, msg
        cache[symbol]={'price':price,'prev':prev,'ts':time.time()}
        return price, prev, 'Online'
    except Exception as e:
        if manual:
            price, prev, msg=manual; cache[symbol]={'price':price,'prev':prev or price,'ts':time.time()}; return price, prev or price, msg
        if cached.get('price'):
            return cached.get('price'), cached.get('prev', cached.get('price')), 'Son kayıt'
        return None, None, str(e)

st.markdown('<div class="big">📊 Kişisel Yatırım Paneli V2.3</div><div class="sub">Portföy düzenleme, yeni varlık ekleme ve kategori özetleri eklendi.</div>', unsafe_allow_html=True)
portfolio=load_portfolio()

with st.sidebar:
    st.header('⚙️ Portföy yönetimi')
    with st.expander('➕ Yeni varlık ekle', expanded=True):
        new_asset=st.text_input('Varlık adı', placeholder='Euro / Sterlin / TUPRS / NVDA')
        new_type=st.selectbox('Tür', TYPE_OPTIONS, format_func=lambda x: TYPE_LABELS[x])
        new_symbol=st.text_input('Sembol', placeholder='EURTRY, GBPTRY, TUPRS, NVDA.US')
        new_qty=st.number_input('Adet / Gram / Döviz miktarı', min_value=0.0, step=0.01, format='%.6f')
        new_buy=st.number_input('Alış fiyatı TL (opsiyonel)', min_value=0.0, step=0.01, format='%.2f')
        if st.button('Varlığı ekle'):
            if not new_asset or not new_symbol:
                st.error('Varlık adı ve sembol gerekli.')
            else:
                add=pd.DataFrame([{'asset':new_asset,'type':new_type,'symbol':new_symbol.upper().strip(),'quantity':new_qty,'buy_price_try':new_buy if new_buy>0 else None}])
                save_portfolio(pd.concat([portfolio, add], ignore_index=True))
                st.success('Varlık eklendi. Sayfa yenileniyor...'); st.rerun()
    with st.expander('✏️ Mevcut portföyü düzenle'):
        st.caption('Adet/miktarları buradan değiştirip kaydedebilirsin. Satırı silersen portföyden çıkar.')
        edited=st.data_editor(portfolio, use_container_width=True, num_rows='dynamic', column_config={
            'type': st.column_config.SelectboxColumn('type', options=TYPE_OPTIONS),
            'quantity': st.column_config.NumberColumn('quantity', format='%.6f'),
            'buy_price_try': st.column_config.NumberColumn('buy_price_try', format='%.2f')
        })
        if st.button('Portföyü kaydet'):
            save_portfolio(edited); st.success('Portföy kaydedildi.'); st.rerun()

c1,c2,c3=st.columns([1,1,4])
force=c1.button('🔄 Fiyatları yenile')
save_today=c2.button('💾 Bugünkü değeri kaydet')
cache=load_cache(); rows=[]
for _,r in portfolio.iterrows():
    price, prev, note=get_price(r, cache, force=force)
    qty=float(r['quantity']); total=price*qty if price is not None else None; prev_total=prev*qty if prev is not None else None
    d=total-prev_total if total is not None and prev_total is not None else None
    d_pct=d/prev_total*100 if d is not None and prev_total else None
    buy=pd.to_numeric(r.get('buy_price_try'), errors='coerce')
    rows.append({'Varlık':r['asset'],'Sembol':r['symbol'],'Kategori':TYPE_LABELS.get(r['type'],r['type']),'Tür':r['type'],'Adet/Miktar':qty,'Fiyat TL':price,'Toplam TL':total,'Günlük Değişim TL':d,'Günlük Değişim %':d_pct,'Alışa Göre K/Z TL':(price-buy)*qty if price is not None and not pd.isna(buy) else None,'Kaynak/Not':note})
save_cache(cache)
df=pd.DataFrame(rows)
total=df['Toplam TL'].dropna().sum(); daily=df['Günlük Değişim TL'].dropna().sum(); daily_pct=(daily/(total-daily)*100) if total and total!=daily else 0
hist=pd.read_csv(HISTORY); now=datetime.now()
def period_change(days):
    if hist.empty: return None
    h=hist.copy(); h['timestamp']=pd.to_datetime(h['timestamp'], errors='coerce')
    older=h[h['timestamp']<=now-timedelta(days=days)]
    if older.empty: return None
    base=float(older.iloc[-1]['total_try']); return (total-base)/base*100 if base else None
weekly=period_change(7); monthly=period_change(30)
if save_today:
    new=pd.DataFrame([{'timestamp':now.isoformat(timespec='seconds'),'total_try':total,'daily_change_try':daily,'weekly_change_try':weekly,'monthly_change_try':monthly}])
    pd.concat([hist,new], ignore_index=True).to_csv(HISTORY,index=False); st.success('Bugünkü portföy değeri kaydedildi.')

m1,m2,m3,m4=st.columns(4)
m1.metric('Toplam Portföy', money(total)); m2.metric('Bugün', money(daily), pct(daily_pct)); m3.metric('Bu Hafta', pct(weekly) if weekly is not None else '-'); m4.metric('Bu Ay', pct(monthly) if monthly is not None else '-')

st.subheader('📌 Kategori özeti')
cat=df.dropna(subset=['Toplam TL']).groupby('Kategori', as_index=False).agg({'Toplam TL':'sum','Günlük Değişim TL':'sum','Alışa Göre K/Z TL':'sum'})
if not cat.empty:
    cat['Portföy Payı %']=cat['Toplam TL']/cat['Toplam TL'].sum()*100
    cat_show=cat.copy(); cat_show['Toplam TL']=cat_show['Toplam TL'].apply(money); cat_show['Günlük Değişim TL']=cat_show['Günlük Değişim TL'].apply(money); cat_show['Alışa Göre K/Z TL']=cat_show['Alışa Göre K/Z TL'].apply(money); cat_show['Portföy Payı %']=cat_show['Portföy Payı %'].apply(lambda x: f'{x:.2f}%'.replace('.',','))
    st.dataframe(cat_show, use_container_width=True, hide_index=True)
else: st.info('Kategori özeti için en az bir fiyat gerekiyor.')

st.subheader('🏆 En çok kazandıran / kaybettiren')
valid=df.dropna(subset=['Günlük Değişim TL'])
if not valid.empty:
    best=valid.sort_values('Günlük Değişim TL', ascending=False).iloc[0]; worst=valid.sort_values('Günlük Değişim TL').iloc[0]
    b1,b2=st.columns(2); b1.success(f"En çok kazandıran: {best['Varlık']} — {money(best['Günlük Değişim TL'])}"); b2.error(f"En çok kaybettiren: {worst['Varlık']} — {money(worst['Günlük Değişim TL'])}")

st.subheader('Varlıklar')
show=df.copy()
for col in ['Fiyat TL','Toplam TL','Günlük Değişim TL','Alışa Göre K/Z TL']: show[col]=show[col].apply(money)
show['Günlük Değişim %']=show['Günlük Değişim %'].apply(pct)
st.dataframe(show.drop(columns=['Tür']), use_container_width=True)

colA,colB=st.columns(2)
with colA:
    st.subheader('📊 Portföy dağılımı')
    pie=df.dropna(subset=['Toplam TL'])
    if not pie.empty and pie['Toplam TL'].sum()>0:
        st.plotly_chart(px.pie(pie, names='Kategori', values='Toplam TL'), use_container_width=True)
with colB:
    st.subheader('📈 Portföy geçmişi')
    hist=pd.read_csv(HISTORY)
    if not hist.empty: st.plotly_chart(px.line(hist, x='timestamp', y='total_try', markers=True), use_container_width=True)
    else: st.caption('Bugünkü değeri kaydet butonuyla grafik oluşmaya başlar.')

st.subheader('📅 İşlem geçmişi')
with st.expander('Yeni işlem ekle'):
    options=['Yeni / listede olmayan varlık...'] + portfolio['asset'].dropna().tolist()
    choice=st.selectbox('Varlık', options)
    a=st.text_input('Varlık adı') if choice.startswith('Yeni') else choice
    act=st.selectbox('İşlem', ['Alış','Satış','Temettü','Komisyon'])
    q=st.number_input('Adet/gram', min_value=0.0, step=0.01, format='%.6f')
    p=st.number_input('Fiyat TL', min_value=0.0, step=0.01, format='%.2f')
    note=st.text_input('Not')
    auto_update=st.checkbox('Alış/Satış sonrası portföy miktarını otomatik güncelle', value=True)
    if st.button('İşlemi kaydet'):
        tx=pd.read_csv(TX)
        new=pd.DataFrame([{'date':now.isoformat(timespec='seconds'),'asset':a,'action':act,'quantity':q,'price_try':p,'note':note}])
        pd.concat([tx,new], ignore_index=True).to_csv(TX,index=False)
        if auto_update and a in portfolio['asset'].values and act in ['Alış','Satış']:
            port=load_portfolio(); idx=port.index[port['asset']==a][0]
            port.loc[idx,'quantity']=float(port.loc[idx,'quantity']) + (q if act=='Alış' else -q)
            if act=='Alış' and p>0: port.loc[idx,'buy_price_try']=p
            save_portfolio(port)
        st.success('İşlem kaydedildi.'); st.rerun()
st.dataframe(pd.read_csv(TX), use_container_width=True)

st.subheader('✍️ Manuel fiyatlar')
st.caption('Online alınamayan varlıklar için TL fiyat gir. Yeni satır ekleyebilirsin.')
manual=pd.read_csv(MANUAL)
missing=pd.DataFrame({'symbol':[s for s in portfolio['symbol'] if s not in manual.get('symbol', pd.Series(dtype=str)).astype(str).str.upper().tolist()], 'price_try':[None]*len(portfolio), 'previous_close_try':[None]*len(portfolio)})[:0]
manual_edit=st.data_editor(manual, use_container_width=True, num_rows='dynamic')
if st.button('Manuel fiyatları kaydet'):
    manual_edit.to_csv(MANUAL,index=False); st.success('Manuel fiyatlar kaydedildi.'); st.rerun()

st.subheader('📥 Raporlar')
excel=io.BytesIO()
with pd.ExcelWriter(excel, engine='openpyxl') as w:
    df.to_excel(w,index=False,sheet_name='Portfoy'); cat.to_excel(w,index=False,sheet_name='Kategori Ozeti'); pd.read_csv(TX).to_excel(w,index=False,sheet_name='Islem Gecmisi'); pd.read_csv(HISTORY).to_excel(w,index=False,sheet_name='Gecmis')
st.download_button('Excel’e aktar', excel.getvalue(), 'yatirim_raporu.xlsx')
st.caption('Telefon: Mac ve telefon aynı Wi‑Fi ağındaysa terminalde görünen Network URL adresini iPhone Safari’de açabilirsin.')
