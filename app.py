from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from database.db import (
    add_alert,
    add_asset,
    add_snapshot,
    add_transaction,
    delete_asset,
    init_db,
    load_alerts,
    load_assets,
    load_snapshots,
    load_transactions,
    save_assets,
)
from reports.exporters import excel_bytes, pdf_bytes
from services.prices import enrich_prices, format_try

APP_VERSION = "V3.1"
APP_TITLE = "Benim Finans"
CATEGORY_OPTIONS = ["Altın", "Döviz", "BIST", "ABD Hisse", "Fon", "Kripto", "BES", "Diğer"]

st.set_page_config(page_title=APP_TITLE, page_icon="💼", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
.block-container {padding-top: 1rem; padding-bottom: 4rem; max-width: 1180px;}
[data-testid="stMetricValue"] {font-size: 1.85rem; font-weight: 800;}
[data-testid="stSidebar"] {background: #0f172a;}
[data-testid="stSidebar"] * {color: #f8fafc !important;}
.bf-card {border: 1px solid #e5e7eb; border-radius: 18px; padding: 18px; background: #fff; box-shadow: 0 1px 10px rgba(15,23,42,.05); min-height: 105px;}
.bf-card h4 {margin: 0 0 6px 0; font-size: .95rem; color: #64748b;}
.bf-card .value {font-size: 1.45rem; font-weight: 800; color: #111827;}
.bf-card .sub {font-size: .85rem; color: #64748b;}
.good {color: #16a34a; font-weight: 700;}
.bad {color: #dc2626; font-weight: 700;}
.muted {color: #64748b; font-size: .9rem;}
@media (max-width: 768px) {
  [data-testid="column"] {width: 100% !important; flex: unset;}
  [data-testid="stMetricValue"] {font-size: 1.45rem;}
  .bf-card {margin-bottom: 10px;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def pct_text(x: float) -> str:
    return f"{x:+.2f}%".replace(".", ",")


def app_header(priced: pd.DataFrame, total: float) -> None:
    st.title("💼 Benim Finans")
    st.caption(f"{APP_VERSION} • Mobil uyumlu kişisel yatırım paneli • Yatırım tavsiyesi değildir.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Portföy", format_try(total))
    c2.metric("Varlık Sayısı", len(priced))
    if not priced.empty and total > 0:
        by_cat = priced.groupby("category", as_index=False)["total_try"].sum().sort_values("total_try", ascending=False)
        c3.metric("En Büyük Kategori", by_cat.iloc[0]["category"])
    else:
        c3.metric("En Büyük Kategori", "-")
    c4.metric("Son Güncelleme", datetime.now().strftime("%H:%M"))


def sidebar_menu() -> str:
    st.sidebar.title("💼 Benim Finans")
    st.sidebar.caption("Kişisel portföy sistemi")
    return st.sidebar.radio(
        "Menü",
        ["🏠 Dashboard", "💰 Portföy", "➕ Varlık Ekle", "🧾 İşlemler", "📈 Grafikler", "🔔 Alarm", "📄 Raporlar", "⚙️ Ayarlar"],
        label_visibility="collapsed",
    )


def dashboard(priced: pd.DataFrame, snapshots: pd.DataFrame, total: float) -> None:
    st.subheader("🏠 Dashboard")
    by_cat = priced.groupby("category", as_index=False)["total_try"].sum().sort_values("total_try", ascending=False)

    cols = st.columns(4)
    for i, cat in enumerate(CATEGORY_OPTIONS[:4]):
        val = float(by_cat.loc[by_cat["category"] == cat, "total_try"].sum()) if not by_cat.empty else 0
        share = (val / total * 100) if total > 0 else 0
        cols[i].markdown(f"""
        <div class='bf-card'>
          <h4>{cat}</h4>
          <div class='value'>{format_try(val)}</div>
          <div class='sub'>Portföy payı: {share:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    left, right = st.columns([1.15, .85])
    with left:
        st.markdown("### Portföy dağılımı")
        positive = by_cat[by_cat["total_try"] > 0]
        if not positive.empty:
            fig = px.pie(positive, names="category", values="total_try", hole=.45)
            fig.update_layout(height=360, margin=dict(l=5, r=5, t=20, b=5), legend_title_text="Kategori")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Fiyatlar geldikçe portföy dağılım grafiği oluşacak. Şimdilik manuel fiyat girebilirsin.")
    with right:
        st.markdown("### Öne çıkanlar")
        tmp = priced.copy()
        if not tmp.empty and tmp["total_try"].sum() > 0:
            top = tmp.sort_values("total_try", ascending=False).iloc[0]
            st.success(f"En büyük varlık: {top['name']} — {format_try(top['total_try'])}")
            if (tmp["pnl_try"].abs().sum() > 0):
                gain = tmp.sort_values("pnl_try", ascending=False).iloc[0]
                loss = tmp.sort_values("pnl_try", ascending=True).iloc[0]
                st.info(f"En çok kazandıran: {gain['name']} — {format_try(gain['pnl_try'])}")
                st.warning(f"En çok kaybettiren: {loss['name']} — {format_try(loss['pnl_try'])}")
        else:
            st.info("Manuel fiyat veya online fiyat gelince özet oluşacak.")

        if st.button("💾 Bugünkü değeri kaydet", use_container_width=True):
            details = priced[["name", "symbol", "category", "quantity", "price_try", "total_try"]].to_json(orient="records", force_ascii=False)
            add_snapshot(total, details)
            st.success("Bugünkü değer kaydedildi.")

    st.markdown("### Varlıklar")
    view = priced[["name", "category", "quantity", "price_try", "total_try", "pnl_try", "source"]].copy()
    view.columns = ["Varlık", "Kategori", "Adet/Gram", "Fiyat TL", "Toplam TL", "K/Z TL", "Kaynak"]
    st.dataframe(view, use_container_width=True, hide_index=True)


def portfolio_page(priced: pd.DataFrame) -> None:
    st.subheader("💰 Portföy")
    st.caption("Miktar, kategori, alış maliyeti ve manuel fiyatı buradan değiştirebilirsin.")
    editable = priced[["id", "name", "symbol", "category", "quantity", "cost_try", "manual_price_try"]].copy()
    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Varlık"),
            "symbol": st.column_config.TextColumn("Sembol"),
            "category": st.column_config.SelectboxColumn("Kategori", options=CATEGORY_OPTIONS),
            "quantity": st.column_config.NumberColumn("Adet/Gram", step=0.0001, format="%.6f"),
            "cost_try": st.column_config.NumberColumn("Alış Maliyeti TL", step=0.01, format="%.2f"),
            "manual_price_try": st.column_config.NumberColumn("Manuel Fiyat TL", step=0.01, format="%.2f"),
        },
        num_rows="dynamic",
    )
    c1, c2 = st.columns([1, 1])
    if c1.button("💾 Portföy değişikliklerini kaydet", use_container_width=True):
        save_assets(edited)
        st.success("Portföy kaydedildi. Sayfa yenileniyor...")
        st.rerun()
    with c2.expander("🗑️ Varlık sil"):
        ids = priced["id"].tolist()
        sel = st.selectbox("Silinecek ID", ids) if ids else None
        if st.button("Seçili varlığı sil") and sel:
            delete_asset(int(sel)); st.success("Silindi."); st.rerun()

    st.markdown("### Kategorilere göre görünüm")
    for cat, g in priced.groupby("category"):
        with st.expander(f"{cat} — {format_try(float(g['total_try'].sum()))}", expanded=False):
            st.dataframe(g[["name", "symbol", "quantity", "price_try", "total_try", "source"]], use_container_width=True, hide_index=True)


def add_asset_page() -> None:
    st.subheader("➕ Varlık Ekle")
    with st.form("asset_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Varlık adı", placeholder="Euro, THYAO, Apple, Bitcoin...")
        symbol = c2.text_input("Sembol", placeholder="EURTRY, THYAO, AAPL.US, BTC...")
        category = c1.selectbox("Kategori", CATEGORY_OPTIONS)
        quantity = c2.number_input("Adet / gram", min_value=0.0, step=0.0001, format="%.6f")
        cost = c1.number_input("Alış maliyeti TL", min_value=0.0, step=0.01)
        manual = c2.number_input("Manuel fiyat TL", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("Varlığı ekle", use_container_width=True)
        if submitted:
            if not name or not symbol:
                st.error("Varlık adı ve sembol gerekli.")
            else:
                add_asset(name, symbol, category, quantity, cost, manual)
                st.success("Varlık eklendi.")
                st.rerun()
    st.info("Örnekler: EURTRY, GBPTRY, THYAO, ASELS, AAPL.US, MSFT.US. Online fiyat gelmezse manuel fiyat kullanılır.")


def transactions_page(priced: pd.DataFrame) -> None:
    st.subheader("🧾 İşlemler")
    names = sorted(set(priced["name"].tolist() + priced["symbol"].tolist())) if not priced.empty else []
    with st.form("tx_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        asset = c1.selectbox("Varlık", names) if names else c1.text_input("Varlık")
        action = c2.selectbox("İşlem", ["Alış", "Satış", "Temettü", "Komisyon", "Nakit"])
        quantity = c1.number_input("Miktar", min_value=0.0, step=0.0001, format="%.6f")
        price = c2.number_input("Fiyat TL", min_value=0.0, step=0.01)
        note = st.text_input("Not")
        if st.form_submit_button("İşlemi kaydet", use_container_width=True):
            add_transaction(asset, action, quantity, price, note)
            st.success("İşlem kaydedildi ve portföye yansıtıldı.")
            st.rerun()
    tx = load_transactions()
    st.markdown("### İşlem geçmişi")
    st.dataframe(tx, use_container_width=True, hide_index=True)


def charts_page(priced: pd.DataFrame, snapshots: pd.DataFrame) -> None:
    st.subheader("📈 Grafikler")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Kategori dağılımı")
        by_cat = priced.groupby("category", as_index=False)["total_try"].sum()
        by_cat = by_cat[by_cat["total_try"] > 0]
        if not by_cat.empty:
            st.plotly_chart(px.bar(by_cat, x="category", y="total_try", text_auto=".2s"), use_container_width=True)
        else:
            st.info("Grafik için fiyat verisi gerekli.")
    with c2:
        st.markdown("#### Portföy geçmişi")
        if not snapshots.empty:
            snapshots["ts"] = pd.to_datetime(snapshots["ts"])
            st.plotly_chart(px.line(snapshots, x="ts", y="total_try", markers=True), use_container_width=True)
        else:
            st.info("Dashboard'daki 'Bugünkü değeri kaydet' butonuyla geçmiş oluşur.")


def alerts_page(priced: pd.DataFrame) -> None:
    st.subheader("🔔 Alarm")
    names = sorted(set(priced["name"].tolist() + priced["symbol"].tolist())) if not priced.empty else []
    with st.form("alert_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        asset = c1.selectbox("Varlık", names) if names else c1.text_input("Varlık")
        op = c2.selectbox("Koşul", [">=", "<="])
        target = c3.number_input("Hedef fiyat TL", min_value=0.0, step=0.01)
        if st.form_submit_button("Alarm ekle", use_container_width=True):
            add_alert(asset, op, target)
            st.success("Alarm eklendi. Bu sürümde alarm listesi hazırlanır; bildirim V3.2'de Telegram/e-posta ile bağlanacak.")
    alerts = load_alerts()
    st.dataframe(alerts, use_container_width=True, hide_index=True)


def reports_page(priced: pd.DataFrame, transactions: pd.DataFrame, snapshots: pd.DataFrame, total: float) -> None:
    st.subheader("📄 Raporlar")
    c1, c2 = st.columns(2)
    c1.download_button("📥 Excel indir", data=excel_bytes(priced, transactions, snapshots), file_name="benimfinans_rapor.xlsx", use_container_width=True)
    c2.download_button("📄 PDF indir", data=pdf_bytes(total, priced), file_name="benimfinans_rapor.pdf", mime="application/pdf", use_container_width=True)
    st.caption("PDF Türkçe karakterleri sadeleştirilmiş yazabilir; V3.2'de daha gelişmiş PDF tasarımı eklenecek.")


def settings_page() -> None:
    st.subheader("⚙️ Ayarlar")
    st.info("Online sürümde Streamlit Cloud dosya sistemi kalıcı veritabanı için sınırlıdır. Verileri önemli gördüğünde Excel raporu indirmeni öneririm. Kalıcı bulut veritabanı V3.2/V3.3 aşamasında eklenebilir.")
    if st.button("🔄 Online fiyat önbelleğini temizle"):
        st.cache_data.clear()
        st.success("Önbellek temizlendi.")
        st.rerun()


def main() -> None:
    init_db()
    assets = load_assets()
    priced = enrich_prices(assets)
    total = float(priced["total_try"].sum()) if not priced.empty else 0
    snapshots = load_snapshots()
    transactions = load_transactions()

    menu = sidebar_menu()
    app_header(priced, total)

    if menu == "🏠 Dashboard":
        dashboard(priced, snapshots, total)
    elif menu == "💰 Portföy":
        portfolio_page(priced)
    elif menu == "➕ Varlık Ekle":
        add_asset_page()
    elif menu == "🧾 İşlemler":
        transactions_page(priced)
    elif menu == "📈 Grafikler":
        charts_page(priced, snapshots)
    elif menu == "🔔 Alarm":
        alerts_page(priced)
    elif menu == "📄 Raporlar":
        reports_page(priced, transactions, snapshots, total)
    elif menu == "⚙️ Ayarlar":
        settings_page()

    st.divider()
    st.caption(f"{APP_VERSION} • Benim Finans • Online fiyat gelmezse manuel fiyat kullanılır.")


if __name__ == "__main__":
    main()
