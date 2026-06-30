import streamlit as st
from supabase import create_client, Client


def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error("Supabase bağlantı bilgileri eksik. Streamlit Secrets kontrol edilmeli.")
        st.stop()

    return create_client(url, key)
