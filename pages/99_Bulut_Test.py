import streamlit as st
import pandas as pd
from database.asset_repository import list_assets, add_asset, delete_asset

st.set_page_config(page_title="Bulut Test", page_icon="☁️")

st.title("☁️ Supabase Bulut Test")

st.info("Bu sayfa Supabase'e veri yazma/okuma testidir.")

with st.form("asset_form"):
    name = st.text_input("Varlık adı", "Test Varlık")
    symbol = st.text_input("Sembol", "TEST")
    category = st.selectbox("Kategori", ["Altın", "Döviz", "BIST", "ABD", "Kripto", "Fon", "Diğer"])
    quantity = st.number_input("Miktar", min_value=0.0, value=1.0)
    avg_cost = st.number_input("Ortalama maliyet", min_value=0.0, value=100.0)
    manual_price = st.number_input("Manuel fiyat", min_value=0.0, value=110.0)

    submitted = st.form_submit_button("Supabase'e Kaydet")

if submitted:
    add_asset(name, symbol, category, quantity, avg_cost, manual_price)
    st.success("Supabase'e kaydedildi.")
    st.rerun()

assets = list_assets()

st.subheader("Buluttaki Varlıklar")

if assets:
    st.dataframe(pd.DataFrame(assets), use_container_width=True)

    delete_id = st.number_input("Silinecek asset id", min_value=1, step=1)
    if st.button("Seçili ID'yi Sil"):
        delete_asset(delete_id)
        st.success("Silindi.")
        st.rerun()
else:
    st.warning("Henüz Supabase'de varlık yok.")
