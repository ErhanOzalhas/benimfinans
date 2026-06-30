from __future__ import annotations
from datetime import date, timedelta
import base64
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px

from database.db import (
    init_db, add_asset, update_asset, assets_df, transactions_df, add_transaction,
    delete_transaction, clear_all_data, archive_asset, restore_asset, delete_asset, backend_name, using_supabase, save_snapshot, snapshots_df
)
from services.prices import refresh_all_prices, get_price_try
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




def parse_tr_number(value, default=0.0):
    """Türkçe sayı girişini float'a çevirir: 1.234,56 -> 1234.56"""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace(" ", "")
    # Hem nokta hem virgül varsa, nokta binlik ayırıcı, virgül ondalık kabul edilir.
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def tr_amount_input(label, key, placeholder="0,00", help=None):
    return st.text_input(label, value="", placeholder=placeholder, key=key, help=help)

def money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out=df.copy()
    for c in cols:
        if c in out.columns: out[c]=out[c].map(tl)
    if 'Getiri %' in out.columns: out['Getiri %']=out['Getiri %'].map(pct)
    return out

inject_branding(); init_db()

# Uygulama açıldığında fiyatları oturum başına bir kez otomatik yenile.
# Manuel yenileme butonu ayrıca kalır.
if 'auto_price_refresh_done' not in st.session_state:
    st.session_state.auto_price_refresh_done = True
    try:
        refresh_all_prices()
    except Exception as e:
        st.warning(f'Otomatik fiyat yenileme tamamlanamadı: {e}')

with st.sidebar:
    st.title('💼 Benim Finans')
    st.caption('MyFin • V6.5 Portfolio Experience')
    page=st.radio('Menü', ['🏠 Ana Sayfa','💼 Portföy','➕ Yeni Varlık','💳 İşlem Defteri','📊 Kâr/Zarar','📈 Grafikler','🧾 Raporlar','⚙️ Ayarlar'], label_visibility='collapsed')
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
  <div class='title'>Benim Finans • MyFin • V6.5 Portfolio Experience</div>
  <div class='value'>{tl(total)}</div>
  <div class='sub'>Toplam K/Z: <span class='{ 'good' if pl>=0 else 'bad' }'>{tl(pl)} ({pct(pl_pct)})</span></div>
</div>
""", unsafe_allow_html=True)

m1,m2,m3,m4=st.columns(4)
m1.metric('Toplam Portföy', tl(total))
m2.metric('Toplam K/Z', tl(pl), pct(pl_pct))
m3.metric('Gerçekleşmiş K/Z', tl(realized))
m4.metric('Gerçekleşmemiş K/Z', tl(unrealized))

c_top1, c_top2 = st.columns(2)
with c_top1:
    if st.button('🔄 Anlık / Online fiyatları güncelle', type='primary', use_container_width=True):
        with st.spinner('Online fiyat kaynakları deneniyor...'):
            res=refresh_all_prices()
        st.success('Fiyat yenileme tamamlandı')
        st.dataframe(res, use_container_width=True, hide_index=True)
        st.rerun()
with c_top2:
    if st.button('💾 Bugünkü portföy değerini kaydet', use_container_width=True):
        save_snapshot(total, pl, 'Manuel günlük kayıt')
        st.success('Bugünkü değer buluta kaydedildi.')
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
        snaps = snapshots_df()
        if not snaps.empty:
            st.subheader('Portföy geçmişi')
            st.plotly_chart(px.line(snaps, x='snapshot_date', y='total_value_try', markers=True, title='Günlük portföy değeri'), use_container_width=True)

elif page=='💼 Portföy':
    st.header('💼 Portföyüm')
    st.caption('Portföy işlem geçmişinden hesaplanır. Önce kategori özetini, sonra varlık detaylarını görebilirsin.')

    tab_kat, tab_varlik, tab_yonet = st.tabs(['📊 Kategori Özeti', '📄 Varlık Detayı', '⚙️ Varlık Yönetimi'])

    with tab_kat:
        if cat.empty:
            st.info('Kategori özeti için önce varlık eklemelisin.')
        else:
            ikonlar = {
                'Altın': '🥇 Altın',
                'Döviz': '💵 Döviz',
                'BIST': '🇹🇷 BIST',
                'BIST Hisse': '🇹🇷 BIST',
                'ABD Hisse': '🇺🇸 ABD Hisse',
                'Kripto': '₿ Kripto',
                'Fon': '📊 Fon',
                'BES': '🏦 BES',
                'Diğer': '📦 Diğer',
            }
            cat_show = cat.copy()
            cat_show['Kategori'] = cat_show['Kategori'].map(lambda x: ikonlar.get(str(x), str(x)))
            if 'Kalan Maliyet TL' in cat_show.columns and 'Güncel Değer TL' in cat_show.columns:
                cat_show['Getiri %'] = cat_show.apply(
                    lambda r: (float(r.get('Toplam K/Z TL', 0)) / float(r.get('Kalan Maliyet TL', 0)) * 100) if float(r.get('Kalan Maliyet TL', 0) or 0) else 0,
                    axis=1,
                )

            k1, k2, k3 = st.columns(3)
            biggest = cat.sort_values('Güncel Değer TL', ascending=False).iloc[0] if not cat.empty else None
            best = cat.sort_values('Toplam K/Z TL', ascending=False).iloc[0] if not cat.empty else None
            k1.metric('Toplam Portföy', tl(total))
            k2.metric('En büyük kategori', biggest['Kategori'] if biggest is not None else '-')
            k3.metric('En çok kazandıran kategori', best['Kategori'] if best is not None else '-')

            cols_to_show = [c for c in ['Kategori','Güncel Değer TL','Kalan Maliyet TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL','Getiri %'] if c in cat_show.columns]
            st.dataframe(
                money_cols(cat_show[cols_to_show], ['Güncel Değer TL','Kalan Maliyet TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL']),
                use_container_width=True,
                hide_index=True,
            )
            st.plotly_chart(px.pie(cat, values='Güncel Değer TL', names='Kategori', hole=.55, title='Kategori Dağılımı'), use_container_width=True)

    with tab_varlik:
        if portfolio.empty:
            st.info('Portföy boş.')
        else:
            compact_cols = [c for c in ['Varlık','Sembol','Kategori','Miktar','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL','Getiri %'] if c in portfolio.columns]
            show = money_cols(portfolio[compact_cols], ['Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL'])
            st.dataframe(show, use_container_width=True, hide_index=True)

            with st.expander('Detaylı portföy tablosu'):
                detay = money_cols(portfolio, ['Ort. Maliyet TL','Kalan Maliyet TL','Güncel Fiyat TL','Güncel Değer TL','Gerçekleşmiş K/Z TL','Gerçekleşmemiş K/Z TL','Toplam K/Z TL','Toplam Alış TL','Toplam Satış TL'])
                st.dataframe(detay, use_container_width=True, hide_index=True)

    with tab_yonet:
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
    st.header('➕ Yeni Varlık / Geçmiş Tarihli Alış')

    def otomatik_sembol(kategori, emtia):
        e = emtia.strip().upper()

        harita = {
            "GRAM ALTIN": "GRAM_ALTIN",
            "ALTIN": "GRAM_ALTIN",
            "DOLAR": "USDTRY",
            "USD": "USDTRY",
            "EURO": "EURTRY",
            "EUR": "EURTRY",
            "STERLIN": "GBPTRY",
            "GBP": "GBPTRY",
        }

        if e in harita:
            return harita[e]

        if kategori == "ABD Hisse":
            return e if e.endswith(".US") else f"{e}.US"

        return e

    def kur_sembolu(para_birimi):
        if para_birimi == 'USD':
            return 'USDTRY'
        if para_birimi == 'EUR':
            return 'EURTRY'
        return None

    with st.form('new_asset'):
        c1, c2 = st.columns(2)
        with c1:
            kategori = st.selectbox('Kategori',['Altın','Döviz','BIST Hisse','ABD Hisse','Kripto','Fon','BES','Diğer'])
        with c2:
            emtia = st.text_input('Emtia / Varlık',placeholder='Gram Altın, Dolar, Euro, ASELS, RKLB')

        c3, c4, c5 = st.columns(3)
        with c3:
            alis_tarihi = st.date_input('Alış tarihi', value=date.today())
        with c4:
            adet_txt = tr_amount_input('Adet / Gram', 'new_adet', '0,00')
            adet = parse_tr_number(adet_txt)
        with c5:
            para_birimi = st.selectbox('Alış para birimi', ['TRY','USD','EUR'], index=0)

        bugun = date.today()
        eski_tarih = alis_tarihi < bugun

        c6, c7 = st.columns(2)
        with c6:
            alis_fiyati_txt = tr_amount_input(
                'Alış fiyatı',
                'new_alis_fiyati',
                '0,00',
                help='Seçtiğin para biriminde gir. Örnek: 12,35 veya 1.234,56'
            )
            alis_fiyati_orijinal = parse_tr_number(alis_fiyati_txt)
        with c7:
            komisyon_txt = tr_amount_input('Komisyon TL', 'new_komisyon', '0,00', help='Alışta maliyete eklenir.')
            komisyon = parse_tr_number(komisyon_txt)

        manuel_tl = 0.0
        kur_bilgisi = ''
        if para_birimi != 'TRY':
            if eski_tarih:
                st.warning('Eski tarihli USD/EUR işlemlerde bugünkü kur kullanılmaz. Lütfen o tarihteki TL karşılığını manuel gir.')
                manuel_tl_txt = tr_amount_input('Alış fiyatı TL manuel', 'new_manuel_tl_eski', '0,00')
                manuel_tl = parse_tr_number(manuel_tl_txt)
                kur_bilgisi = 'Manuel tarihsel TL fiyat kullanıldı'
            else:
                fx_symbol = kur_sembolu(para_birimi)
                try:
                    kur, kaynak = get_price_try(fx_symbol, 'Döviz', 0)
                    kur_bilgisi = f'{para_birimi}/TRY güncel kur: {kur:,.4f} ({kaynak})'
                    st.info(kur_bilgisi)
                except Exception:
                    kur = 0
                    st.warning('Güncel kur alınamadı. TL karşılığı manuel girilebilir.')
                    manuel_tl_txt = tr_amount_input('Alış fiyatı TL manuel', 'new_manuel_tl_kur_yok', '0,00')
                    manuel_tl = parse_tr_number(manuel_tl_txt)
        else:
            kur = 1

        c8, c9 = st.columns(2)
        with c8:
            manuel_fiyat_txt = tr_amount_input('Manuel güncel fiyat TL', 'new_manuel_fiyat', '0,00')
            manuel_fiyat = parse_tr_number(manuel_fiyat_txt)
        with c9:
            not_alani = st.text_input('Not')

        if st.form_submit_button('✅ Kaydet', type='primary'):
            if not emtia:
                st.error('Emtia / varlık adı gerekli.')
            elif adet <= 0:
                st.error('Adet / gram 0’dan büyük olmalı.')
            elif alis_fiyati_orijinal <= 0:
                st.error('Alış fiyatı girilmeli.')
            else:
                if para_birimi == 'TRY':
                    alis_fiyati_tl = alis_fiyati_orijinal
                elif eski_tarih:
                    if manuel_tl <= 0:
                        st.error('Eski tarihli USD/EUR işlem için manuel TL alış fiyatı girilmeli.')
                        st.stop()
                    alis_fiyati_tl = manuel_tl
                else:
                    if kur <= 0:
                        if manuel_tl <= 0:
                            st.error('Kur alınamadı. Manuel TL fiyat girilmeli.')
                            st.stop()
                        alis_fiyati_tl = manuel_tl
                    else:
                        alis_fiyati_tl = alis_fiyati_orijinal * kur

                sembol = otomatik_sembol(kategori, emtia)
                detay_not = not_alani or ''
                if para_birimi != 'TRY':
                    detay_not = (detay_not + ' | ' if detay_not else '') + f'Alış: {alis_fiyati_orijinal} {para_birimi}; TL fiyat: {alis_fiyati_tl:.2f}; {kur_bilgisi}'

                add_asset(emtia, sembol, kategori, manual_price_try=manuel_fiyat)
                add_transaction(alis_tarihi, sembol, 'Alış', adet, alis_fiyati_tl, komisyon, detay_not)
                st.success(f'{emtia} kaydedildi. Otomatik sembol: {sembol}. Alış fiyatı TL: {alis_fiyati_tl:,.2f}')
                st.rerun()

elif page=='💳 İşlem Defteri':
    st.header('💳 İşlem Defteri')
    st.info('Bu ekran, mevcut bir varlığa sonradan alış/satış/temettü/komisyon işlemi eklemek içindir. İlk alış için ➕ Yeni Varlık ekranını kullanabilirsin.')
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
            qty_txt=c4.text_input('Adet / Gram', value='', placeholder='0,00', key='tx_qty')
            price_txt=c5.text_input('İşlem fiyatı TL', value='', placeholder='0,00', key='tx_price')
            commission_txt=c6.text_input('Komisyon TL', value='', placeholder='0,00', key='tx_commission')
            qty=parse_tr_number(qty_txt)
            price=parse_tr_number(price_txt)
            commission=parse_tr_number(commission_txt)
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
        st.warning('Supabase secrets bulunamadı. Yerel geliştirme için SQLite kullanılıyor. Online kalıcı kullanım için Streamlit Secrets içine SUPABASE_URL ve SUPABASE_ANON_KEY ekle.')
    st.subheader('🧹 Tüm veriyi sıfırla')
    confirm=st.checkbox('Tüm portföyü, işlemleri ve fiyat önbelleğini silmeyi onaylıyorum')
    if st.button('🗑️ Tüm portföyü temizle', type='primary', disabled=not confirm):
        clear_all_data(); st.success('Portföy tamamen temizlendi.'); st.rerun()
