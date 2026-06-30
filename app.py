from __future__ import annotations
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
from database.db import init_db, add_asset, update_asset, assets_df, transactions_df, add_transaction, delete_transaction
from services.prices import refresh_all_prices
from services.portfolio_engine import build_portfolio, category_summary, date_range_analysis

st.set_page_config(page_title='Benim Finans', page_icon='💼', layout='wide')

st.markdown('''
<style>
[data-testid="stSidebar"]{background:#0f172a;color:white;}
.metric-card{border:1px solid #e5e7eb;border-radius:18px;padding:18px;background:white;box-shadow:0 2px 12px rgba(15,23,42,.05)}
.big-number{font-size:34px;font-weight:800;color:#1f2937}
.good{color:#16a34a;font-weight:700}.bad{color:#dc2626;font-weight:700}
.stButton>button{border-radius:12px;font-weight:700}
</style>
''', unsafe_allow_html=True)

init_db()

def tl(x):
    try: return f"{float(x):,.2f} TL".replace(',', 'X').replace('.', ',').replace('X','.')
    except Exception: return '-'

def pct(x):
    try: return f"{float(x):+.2f}%".replace('.', ',')
    except Exception: return '-'

with st.sidebar:
    st.title('💼 Benim Finans')
    st.caption('V4.0 Portföy Motoru')
    page=st.radio('Menü', ['🏠 Dashboard','💼 Portföy','➕ Yeni Varlık','💳 İşlem Ekle','📊 Kâr/Zarar','📈 Grafikler','🧾 Raporlar','⚙️ Ayarlar'], label_visibility='collapsed')
    st.divider()
    if st.button('🔄 Fiyatları yenile', use_container_width=True):
        with st.spinner('Fiyatlar güncelleniyor...'):
            res=refresh_all_prices()
        st.success('Fiyatlar güncellendi')
        st.dataframe(res, use_container_width=True)

st.title('💼 Benim Finans')
st.caption('V4.0 • SQLite işlem motoru • Geçmiş tarihli işlemler • Kâr/Zarar analizi • Yatırım tavsiyesi değildir.')

portfolio=build_portfolio()
cat=category_summary()
total=float(portfolio['Güncel Değer TL'].sum()) if not portfolio.empty else 0
pl=float(portfolio['Toplam K/Z TL'].sum()) if not portfolio.empty else 0
realized=float(portfolio['Gerçekleşmiş K/Z TL'].sum()) if not portfolio.empty else 0
unrealized=float(portfolio['Gerçekleşmemiş K/Z TL'].sum()) if not portfolio.empty else 0

c1,c2,c3,c4=st.columns(4)
c1.metric('Toplam Portföy', tl(total))
c2.metric('Toplam K/Z', tl(pl), pct((pl/(total-pl)*100) if (total-pl) else 0))
c3.metric('Gerçekleşmiş K/Z', tl(realized))
c4.metric('Gerçekleşmemiş K/Z', tl(unrealized))

if st.button('🔄 Fiyatları yenile', type='primary', use_container_width=True):
    with st.spinner('Online fiyat kaynakları deneniyor...'):
        res=refresh_all_prices()
    st.success('Fiyat yenileme tamamlandı')
    st.dataframe(res, use_container_width=True)
    st.rerun()

st.divider()

if page=='🏠 Dashboard':
    st.header('🏠 Dashboard')
    if not cat.empty:
        left,right=st.columns([1,1])
        with left:
            st.subheader('Kategori kartları')
            for _,r in cat.sort_values('Güncel Değer TL', ascending=False).iterrows():
                st.markdown(f"""<div class='metric-card'><b>{r['Kategori']}</b><div class='big-number'>{tl(r['Güncel Değer TL'])}</div><span class={'good' if r['Toplam K/Z TL']>=0 else 'bad'}>{tl(r['Toplam K/Z TL'])}</span></div><br>""", unsafe_allow_html=True)
        with right:
            st.subheader('Portföy dağılımı')
            fig=px.pie(cat, values='Güncel Değer TL', names='Kategori', hole=.55)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('Henüz portföy yok.')

elif page=='💼 Portföy':
    st.header('💼 Portföy')
    st.caption('Portföy artık işlem geçmişinden hesaplanır. Miktar değiştirmek için alış/satış işlemi ekle. Manuel fiyat ve kategori düzenleyebilirsin.')
    if portfolio.empty:
        st.info('Portföy boş.')
    else:
        show=portfolio.copy()
        for col in ['Ort. Maliyet TL','Kalan Maliyet TL','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL']:
            show[col]=show[col].map(tl)
        show['Getiri %']=portfolio['Getiri %'].map(pct)
        st.dataframe(show, use_container_width=True, hide_index=True)

    st.subheader('Varlık bilgilerini düzenle')
    assets=assets_df(active_only=False)
    edited=st.data_editor(assets[['name','symbol','category','manual_price_try','active']], use_container_width=True, disabled=['symbol'], num_rows='fixed')
    if st.button('💾 Varlık bilgilerini kaydet'):
        for _,r in edited.iterrows():
            update_asset(r['symbol'], r['name'], r['category'], r['manual_price_try'], r['active'])
        st.success('Kaydedildi'); st.rerun()

elif page=='➕ Yeni Varlık':
    st.header('➕ Yeni Varlık + İlk Alış')
    st.caption('Yeni varlığı eklerken geçmiş tarihli ilk alışını da girebilirsin.')
    with st.form('new_asset'):
        c1,c2=st.columns(2)
        name=c1.text_input('Varlık adı', placeholder='Örn: Euro, ASELS, Bitcoin')
        symbol=c2.text_input('Sembol', placeholder='Örn: EURTRY, ASELS, BTC')
        category=st.selectbox('Kategori', ['Altın','Döviz','BIST','ABD Hisse','Kripto','Fon','BES','Diğer'])
        c3,c4,c5=st.columns(3)
        qty=c3.number_input('Adet / Gram', min_value=0.0, value=0.0, step=0.01, format='%.6f')
        buy_date=c4.date_input('Alış tarihi', value=date.today())
        buy_price=c5.number_input('Alış fiyatı TL', min_value=0.0, value=0.0, step=0.01)
        c6,c7=st.columns(2)
        commission=c6.number_input('Komisyon TL', min_value=0.0, value=0.0, step=0.01)
        manual_price=c7.number_input('Manuel güncel fiyat TL', min_value=0.0, value=0.0, step=0.01)
        note=st.text_input('Not', placeholder='İlk alım, eski işlem aktarımı vb.')
        ok=st.form_submit_button('✅ Varlığı ve ilk alışı kaydet', type='primary')
        if ok:
            if not name or not symbol:
                st.error('Varlık adı ve sembol gerekli.')
            else:
                sym=symbol.strip().upper()
                add_asset(name, sym, category, manual_price_try=manual_price)
                if qty>0:
                    add_transaction(buy_date, sym, 'Alış', qty, buy_price, commission, note)
                st.success('Varlık ve alış işlemi kaydedildi.'); st.rerun()

elif page=='💳 İşlem Ekle':
    st.header('💳 İşlem Ekle')
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
        st.subheader('İşlem geçmişi')
        tx=transactions_df()
        st.dataframe(tx, use_container_width=True, hide_index=True)
        with st.expander('🗑️ İşlem sil'):
            if not tx.empty:
                del_id=st.selectbox('Silinecek işlem ID', tx['id'].tolist())
                if st.button('İşlemi sil'):
                    delete_transaction(del_id); st.success('Silindi'); st.rerun()

elif page=='📊 Kâr/Zarar':
    st.header('📊 Kâr/Zarar Analizi')
    st.subheader('Varlık bazında')
    if not portfolio.empty:
        pl_df=portfolio[['Varlık','Sembol','Kategori','Miktar','Ort. Maliyet TL','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL','Getiri %']]
        st.dataframe(pl_df, use_container_width=True, hide_index=True)
        st.subheader('Kategori bazında')
        st.dataframe(cat, use_container_width=True, hide_index=True)
    st.subheader('Tarih aralığı analizi')
    c1,c2=st.columns(2)
    start=c1.date_input('Başlangıç', value=date.today()-timedelta(days=30))
    end=c2.date_input('Bitiş', value=date.today())
    txr,summary=date_range_analysis(start,end)
    s1,s2,s3,s4=st.columns(4)
    s1.metric('Alış toplamı', tl(summary.get('buy_total',0)))
    s2.metric('Satış toplamı', tl(summary.get('sell_total',0)))
    s3.metric('Temettü', tl(summary.get('dividend',0)))
    s4.metric('Net nakit akışı', tl(summary.get('net_cash',0)))
    st.dataframe(txr, use_container_width=True, hide_index=True)
    st.caption('Not: Tarih aralığı bölümü seçilen aralıktaki işlemleri ve nakit etkisini gösterir. Güncel gerçekleşmemiş K/Z portföy ekranında izlenir.')

elif page=='📈 Grafikler':
    st.header('📈 Grafikler')
    if not portfolio.empty:
        fig=px.bar(portfolio, x='Varlık', y='Toplam K/Z TL', color='Kategori', title='Varlık bazında toplam K/Z')
        st.plotly_chart(fig, use_container_width=True)
        fig2=px.pie(cat, names='Kategori', values='Güncel Değer TL', hole=.5, title='Kategori dağılımı')
        st.plotly_chart(fig2, use_container_width=True)

elif page=='🧾 Raporlar':
    st.header('🧾 Raporlar')
    st.download_button('📥 Portföy CSV indir', portfolio.to_csv(index=False).encode('utf-8-sig'), 'benimfinans_portfoy.csv', 'text/csv')
    tx=transactions_df()
    st.download_button('📥 İşlemler CSV indir', tx.to_csv(index=False).encode('utf-8-sig'), 'benimfinans_islemler.csv', 'text/csv')

elif page=='⚙️ Ayarlar':
    st.header('⚙️ Ayarlar')
    st.info('V4.0 SQLite işlem motoru aktif. Veritabanı: data/benimfinans.db')
    st.write('Online sürümde veri kalıcılığı Streamlit Cloud dosya sistemine bağlıdır. Uzun vadede Supabase/Firebase/Postgres kullanacağız.')
