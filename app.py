from __future__ import annotations
from datetime import date, timedelta
import base64
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px

from database.db import (
    init_db, add_asset, update_asset, assets_df, transactions_df, add_transaction,
    delete_transaction, clear_all_data, archive_asset, restore_asset, delete_asset, backend_name, using_supabase
)
from services.prices import refresh_all_prices
from services.portfolio_engine import build_portfolio, category_summary, date_range_analysis

st.set_page_config(page_title='Benim Finans', page_icon='💼', layout='wide')


def inject_branding():
    logo = Path('assets/logo.svg')
    if logo.exists():
        b64 = base64.b64encode(logo.read_bytes()).decode()
        st.markdown(f"""
        <link rel="manifest" href="assets/manifest.json">
        <meta name="theme-color" content="#0F172A">
        <link rel="apple-touch-icon" href="data:image/svg+xml;base64,{b64}">
        """, unsafe_allow_html=True)
    st.markdown('''
    <style>
    .main {background:#f8fafc;}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#0f172a,#111827);color:white;}
    [data-testid="stSidebar"] *{color:white!important;}
    .hero{border-radius:26px;padding:24px;background:linear-gradient(135deg,#0f172a,#1e293b);color:white;margin-bottom:18px;box-shadow:0 16px 40px rgba(15,23,42,.18)}
    .hero .title{font-size:18px;opacity:.85}.hero .value{font-size:40px;font-weight:900;letter-spacing:-1px}.hero .sub{font-size:16px;opacity:.9}
    .card{border:1px solid #e5e7eb;border-radius:22px;padding:18px;background:white;box-shadow:0 8px 30px rgba(15,23,42,.06);margin-bottom:12px}
    .card-title{font-weight:800;color:#334155}.card-value{font-size:26px;font-weight:900;color:#0f172a}.good{color:#16a34a;font-weight:800}.bad{color:#dc2626;font-weight:800}
    .stButton>button{border-radius:14px;font-weight:800;border:1px solid #cbd5e1}.stDataFrame{border-radius:18px;overflow:hidden}
    @media(max-width: 768px){.hero .value{font-size:30px}.block-container{padding:1rem .7rem}.card-value{font-size:22px}}
    </style>
    ''', unsafe_allow_html=True)


def tl(x):
    try: return f"{float(x):,.2f} TL".replace(',', 'X').replace('.', ',').replace('X','.')
    except Exception: return '-'


def pct(x):
    try: return f"{float(x):+.2f}%".replace('.', ',')
    except Exception: return '-'


def money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out=df.copy()
    for c in cols:
        if c in out.columns: out[c]=out[c].map(tl)
    if 'Getiri %' in out.columns: out['Getiri %']=out['Getiri %'].map(pct)
    return out

inject_branding(); init_db()

with st.sidebar:
    st.title('💼 Benim Finans')
    st.caption('MyFin • V6.0 Cloud DB')
    page=st.radio('Menü', ['🏠 Ana Sayfa','💼 Portföy','➕ Yeni Varlık','💳 İşlemler','📊 Kâr/Zarar','📈 Grafikler','🧾 Raporlar','⚙️ Ayarlar'], label_visibility='collapsed')
    st.divider()
    if st.button('🔄 Fiyatları yenile', use_container_width=True, type='primary'):
        with st.spinner('Fiyat kaynakları deneniyor...'):
            res=refresh_all_prices()
        st.success('Fiyat yenileme tamamlandı')
        st.dataframe(res, use_container_width=True, hide_index=True)
        st.rerun()

portfolio=build_portfolio()
cat=category_summary()
total=float(portfolio['Güncel Değer TL'].sum()) if not portfolio.empty else 0
pl=float(portfolio['Toplam K/Z TL'].sum()) if not portfolio.empty else 0
base=total-pl
pl_pct=(pl/base*100) if base else 0
realized=float(portfolio['Gerçekleşmiş K/Z TL'].sum()) if not portfolio.empty else 0
unrealized=float(portfolio['Gerçekleşmemiş K/Z TL'].sum()) if not portfolio.empty else 0

st.markdown(f"""
<div class='hero'>
  <div class='title'>Benim Finans • MyFin • V6 Cloud</div>
  <div class='value'>{tl(total)}</div>
  <div class='sub'>Toplam K/Z: <span class='{ 'good' if pl>=0 else 'bad' }'>{tl(pl)} ({pct(pl_pct)})</span></div>
</div>
""", unsafe_allow_html=True)

m1,m2,m3,m4=st.columns(4)
m1.metric('Toplam Portföy', tl(total))
m2.metric('Toplam K/Z', tl(pl), pct(pl_pct))
m3.metric('Gerçekleşmiş K/Z', tl(realized))
m4.metric('Gerçekleşmemiş K/Z', tl(unrealized))

if st.button('🔄 Anlık / Online fiyatları güncelle', type='primary', use_container_width=True):
    with st.spinner('Online fiyat kaynakları deneniyor...'):
        res=refresh_all_prices()
    st.success('Fiyat yenileme tamamlandı')
    st.dataframe(res, use_container_width=True, hide_index=True)
    st.rerun()

st.divider()

if page=='🏠 Ana Sayfa':
    st.header('🏠 Ana Sayfa')
    if cat.empty:
        st.info('Portföy boş. ➕ Yeni Varlık ekranından geçmiş tarihli ilk alımlarını girerek başlayabilirsin.')
    else:
        cols=st.columns(min(4, len(cat)))
        for i,(_,r) in enumerate(cat.sort_values('Güncel Değer TL', ascending=False).iterrows()):
            with cols[i % len(cols)]:
                st.markdown(f"""<div class='card'><div class='card-title'>{r['Kategori']}</div><div class='card-value'>{tl(r['Güncel Değer TL'])}</div><div class='{ 'good' if r['Toplam K/Z TL']>=0 else 'bad' }'>{tl(r['Toplam K/Z TL'])}</div></div>""", unsafe_allow_html=True)
        left,right=st.columns([1,1])
        with left:
            st.subheader('Kategori Dağılımı')
            st.plotly_chart(px.pie(cat, values='Güncel Değer TL', names='Kategori', hole=.55), use_container_width=True)
        with right:
            st.subheader('En çok kazandıran/kaybettiren')
            top=portfolio.sort_values('Toplam K/Z TL', ascending=False).head(5)
            st.dataframe(money_cols(top[['Varlık','Kategori','Toplam K/Z TL','Getiri %']], ['Toplam K/Z TL']), use_container_width=True, hide_index=True)

elif page=='💼 Portföy':
    st.header('💼 Portföy Yönetimi')
    st.caption('Portföy işlem geçmişinden hesaplanır. Ürünleri tek tek arşivleyebilir veya tüm işlem geçmişiyle birlikte silebilirsin.')
    if portfolio.empty:
        st.info('Portföy boş.')
    else:
        show=money_cols(portfolio, ['Ort. Maliyet TL','Kalan Maliyet TL','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL','Toplam Alış TL','Toplam Satış TL'])
        st.dataframe(show, use_container_width=True, hide_index=True)

    st.subheader('Varlık bilgilerini düzenle')
    assets=assets_df(active_only=False, include_archived=True)
    if not assets.empty:
        edit_cols=['name','symbol','category','manual_price_try','active','archived']
        edited=st.data_editor(assets[edit_cols], use_container_width=True, disabled=['symbol'], num_rows='fixed')
        if st.button('💾 Varlık bilgilerini kaydet'):
            for _,r in edited.iterrows():
                update_asset(r['symbol'], r['name'], r['category'], r['manual_price_try'], r['active'])
                if bool(r.get('archived',0)): archive_asset(r['symbol'])
                else: restore_asset(r['symbol'])
            st.success('Kaydedildi'); st.rerun()

        st.subheader('🗑️ Ürün sil / arşivle')
        c1,c2=st.columns(2)
        sym=c1.selectbox('Ürün seç', assets['symbol'].tolist(), format_func=lambda s: f"{assets[assets.symbol==s].iloc[0]['name']} ({s})")
        mode=c2.radio('İşlem', ['Arşivle', 'Kalıcı sil'], horizontal=True)
        confirm=st.checkbox(f'{sym} için işlemi onaylıyorum')
        if st.button('Uygula', disabled=not confirm):
            if mode=='Arşivle': archive_asset(sym); st.success(f'{sym} arşivlendi.')
            else: delete_asset(sym, delete_transactions=True); st.success(f'{sym} ve işlem geçmişi silindi.')
            st.rerun()
    else:
        st.info('Henüz kayıtlı varlık yok.')

elif page=='➕ Yeni Varlık':
    st.header('➕ Yeni Varlık + Geçmiş Tarihli İlk Alış')
    with st.form('new_asset'):
        c1,c2=st.columns(2)
        name=c1.text_input('Varlık adı', placeholder='Euro, ASELS, Bitcoin')
        symbol=c2.text_input('Sembol', placeholder='EUR, ASELS, BTC')
        category=st.selectbox('Kategori', ['Altın','Döviz','BIST','ABD Hisse','Kripto','Fon','BES','Diğer'])
        c3,c4,c5=st.columns(3)
        qty=c3.number_input('Adet / Gram', min_value=0.0, value=0.0, step=0.01, format='%.6f')
        buy_date=c4.date_input('Alış tarihi', value=date.today())
        buy_price=c5.number_input('Alış fiyatı TL', min_value=0.0, value=0.0, step=0.01)
        c6,c7=st.columns(2)
        commission=c6.number_input('Komisyon TL', min_value=0.0, value=0.0, step=0.01)
        manual_price=c7.number_input('Manuel güncel fiyat TL', min_value=0.0, value=0.0, step=0.01)
        note=st.text_input('Not')
        if st.form_submit_button('✅ Kaydet', type='primary'):
            if not name or not symbol:
                st.error('Varlık adı ve sembol gerekli.')
            else:
                sym=symbol.strip().upper(); add_asset(name, sym, category, manual_price_try=manual_price)
                if qty>0: add_transaction(buy_date, sym, 'Alış', qty, buy_price, commission, note)
                st.success('Varlık kaydedildi.'); st.rerun()

elif page=='💳 İşlemler':
    st.header('💳 İşlem Ekle ve Yönet')
    assets=assets_df()
    if assets.empty:
        st.warning('Önce varlık ekle.')
    else:
        with st.form('tx'):
            c1,c2,c3=st.columns(3)
            tx_date=c1.date_input('İşlem tarihi', value=date.today())
            sym=c2.selectbox('Varlık', assets['symbol'].tolist(), format_func=lambda s: f"{assets[assets.symbol==s].iloc[0]['name']} ({s})")
            action=c3.selectbox('İşlem türü', ['Alış','Satış','Temettü','Komisyon'])
            c4,c5,c6=st.columns(3)
            qty=c4.number_input('Adet / Gram', min_value=0.0, value=0.0, step=0.01, format='%.6f')
            price=c5.number_input('İşlem fiyatı TL', min_value=0.0, value=0.0, step=0.01)
            commission=c6.number_input('Komisyon TL', min_value=0.0, value=0.0, step=0.01)
            note=st.text_input('Not')
            if st.form_submit_button('💾 İşlemi kaydet', type='primary'):
                add_transaction(tx_date, sym, action, qty, price, commission, note)
                st.success('İşlem kaydedildi.'); st.rerun()
    tx=transactions_df()
    st.subheader('İşlem geçmişi')
    st.dataframe(tx, use_container_width=True, hide_index=True)
    if not tx.empty:
        with st.expander('🗑️ İşlem sil'):
            del_id=st.selectbox('Silinecek işlem ID', tx['id'].tolist())
            if st.button('İşlemi sil'):
                delete_transaction(del_id); st.success('Silindi'); st.rerun()

elif page=='📊 Kâr/Zarar':
    st.header('📊 Kâr/Zarar Analizi')
    if not portfolio.empty:
        st.dataframe(money_cols(portfolio, ['Ort. Maliyet TL','Kalan Maliyet TL','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL']), use_container_width=True, hide_index=True)
        st.subheader('Kategori bazında')
        st.dataframe(money_cols(cat, ['Güncel Değer TL','Kalan Maliyet TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL']), use_container_width=True, hide_index=True)
    st.subheader('Tarih aralığı')
    c1,c2=st.columns(2)
    start=c1.date_input('Başlangıç', value=date.today()-timedelta(days=30))
    end=c2.date_input('Bitiş', value=date.today())
    txr,summary=date_range_analysis(start,end)
    s1,s2,s3,s4=st.columns(4)
    s1.metric('Alış', tl(summary.get('buy_total',0)))
    s2.metric('Satış', tl(summary.get('sell_total',0)))
    s3.metric('Temettü', tl(summary.get('dividend',0)))
    s4.metric('Net nakit', tl(summary.get('net_cash',0)))
    st.dataframe(txr, use_container_width=True, hide_index=True)

elif page=='📈 Grafikler':
    st.header('📈 Grafikler')
    if not portfolio.empty:
        st.plotly_chart(px.bar(portfolio, x='Varlık', y='Toplam K/Z TL', color='Kategori', title='Varlık bazında toplam K/Z'), use_container_width=True)
        st.plotly_chart(px.pie(cat, names='Kategori', values='Güncel Değer TL', hole=.55, title='Kategori dağılımı'), use_container_width=True)

elif page=='🧾 Raporlar':
    st.header('🧾 Raporlar')
    st.download_button('📥 Portföy CSV indir', portfolio.to_csv(index=False).encode('utf-8-sig'), 'benimfinans_portfoy.csv', 'text/csv')
    tx=transactions_df()
    st.download_button('📥 İşlemler CSV indir', tx.to_csv(index=False).encode('utf-8-sig'), 'benimfinans_islemler.csv', 'text/csv')

elif page=='⚙️ Ayarlar':
    st.header('⚙️ Ayarlar')
    st.info(f'Veri altyapısı: {backend_name()}')
    if using_supabase():
        st.success('Supabase aktif: Telefondan veya bilgisayardan yapılan değişiklikler bulutta kalıcı saklanır.')
    else:
        st.warning('Supabase secrets bulunamadı. Yerel geliştirme için SQLite kullanılıyor. Online kalıcı kullanım için Streamlit Secrets içine SUPABASE_URL ve SUPABASE_KEY ekle.')
    st.subheader('🧹 Tüm veriyi sıfırla')
    confirm=st.checkbox('Tüm portföyü, işlemleri ve fiyat önbelleğini silmeyi onaylıyorum')
    if st.button('🗑️ Tüm portföyü temizle', type='primary', disabled=not confirm):
        clear_all_data(); st.success('Portföy tamamen temizlendi.'); st.rerun()
