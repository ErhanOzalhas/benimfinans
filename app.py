from __future__ import annotations
from datetime import date, timedelta
import base64
import requests
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


BF_LOGO_SVG = """
<svg viewBox="0 0 96 96" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Benim Finans logo">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#061533"/><stop offset="1" stop-color="#1455D9"/></linearGradient>
    <linearGradient id="bar" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#38BDF8"/><stop offset="1" stop-color="#2563EB"/></linearGradient>
    <linearGradient id="arrow" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#16A34A"/><stop offset="1" stop-color="#84CC16"/></linearGradient>
  </defs>
  <rect x="5" y="5" width="86" height="86" rx="22" fill="url(#bg)"/>
  <rect x="24" y="50" width="11" height="24" rx="4" fill="url(#bar)"/>
  <rect x="41" y="38" width="11" height="36" rx="4" fill="url(#bar)"/>
  <rect x="58" y="25" width="11" height="49" rx="4" fill="url(#bar)"/>
  <path d="M20 72 C38 65, 53 52, 72 25" fill="none" stroke="url(#arrow)" stroke-width="7" stroke-linecap="round"/>
  <path d="M70 18 L82 18 L82 30" fill="none" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M72 24 L82 18" fill="none" stroke="white" stroke-width="6" stroke-linecap="round"/>
</svg>
"""


def bf_logo_html(size=74):
    return f"<div class='bf-logo-svg' style='width:{size}px;height:{size}px'>{BF_LOGO_SVG}</div>"


def inject_branding():
    """Benim Finans V6.8 görsel kimliği: beyaz zemin, lacivert/mavi marka dili, mobil uyumlu kartlar."""
    logo = Path('assets/logo.svg')
    if logo.exists():
        b64 = base64.b64encode(logo.read_bytes()).decode()
        st.markdown(f"""
        <link rel="manifest" href="assets/manifest.json">
        <meta name="theme-color" content="#FFFFFF">
        <link rel="apple-touch-icon" href="data:image/svg+xml;base64,{b64}">
        """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    :root{--bf-navy:#071A3A;--bf-blue:#1455D9;--bf-blue2:#2563EB;--bf-sky:#EAF3FF;--bf-green:#16A34A;--bf-red:#DC2626;--bf-text:#0F172A;--bf-muted:#64748B;--bf-line:#E5EAF2;--bf-bg:#FBFDFF;}
    html, body, [data-testid="stAppViewContainer"]{background:var(--bf-bg)!important;color:var(--bf-text)!important;}
    .main .block-container{max-width:1380px;padding-top:1.35rem;padding-bottom:3rem;}
    header[data-testid="stHeader"]{background:rgba(255,255,255,.72);backdrop-filter:blur(14px);border-bottom:1px solid rgba(226,232,240,.75)}
    [data-testid="stSidebar"]{background:#FFFFFF!important;border-right:1px solid var(--bf-line);box-shadow:12px 0 35px rgba(15,23,42,.035);}
    [data-testid="stSidebar"] *{color:var(--bf-text)!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label{border-radius:14px!important;padding:.38rem .55rem!important;margin:.15rem 0!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#F1F6FF!important;}
    [data-testid="stSidebar"] [aria-checked="true"]{background:linear-gradient(135deg,#0B3EA8,#1455D9)!important;border-radius:14px!important;box-shadow:0 10px 20px rgba(20,85,217,.18)!important;}
    [data-testid="stSidebar"] [aria-checked="true"] *{color:white!important;}
    .bf-sidebar-brand{display:flex;align-items:center;gap:10px;padding:.35rem .1rem 1rem .1rem;}
    .bf-sidebar-logo{width:42px;height:42px;border-radius:14px;background:linear-gradient(145deg,#071A3A,#1455D9);display:flex;align-items:center;justify-content:center;color:white;font-size:22px;box-shadow:0 10px 24px rgba(20,85,217,.25)}
    .bf-sidebar-title{font-size:18px;font-weight:900;letter-spacing:-.02em;color:var(--bf-navy)}
    .bf-sidebar-sub{font-size:12px;color:var(--bf-muted)!important;font-weight:700;margin-top:-2px}
    .bf-topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:4px 0 22px 0;}
    .bf-brand{display:flex;align-items:center;gap:16px;}
    .bf-logo{width:76px;height:76px;border-radius:22px;background:linear-gradient(145deg,#071A3A,#0B3EA8 56%,#2563EB);display:flex;align-items:center;justify-content:center;box-shadow:0 18px 40px rgba(20,85,217,.22);font-size:38px;color:white;}
    .bf-title{font-size:42px;font-weight:950;letter-spacing:-.045em;line-height:1;color:var(--bf-navy);}
    .bf-title span{color:var(--bf-blue);}
    .bf-subtitle{font-size:15px;color:#475569;font-weight:650;margin-top:8px;}
    .bf-status{display:flex;align-items:center;gap:18px;flex-wrap:wrap;justify-content:flex-end;}
    .bf-pill{border:1px solid var(--bf-line);background:white;border-radius:999px;padding:9px 14px;font-weight:800;color:var(--bf-navy);box-shadow:0 8px 22px rgba(15,23,42,.05);}
    .bf-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--bf-green);margin-right:7px;box-shadow:0 0 0 5px rgba(22,163,74,.10);}
    .bf-version{background:#EAF3FF;color:#1455D9;border:1px solid #D7E7FF;border-radius:999px;padding:9px 14px;font-weight:900;}
    .bf-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:10px 0 18px;}
    .bf-kpi{background:white;border:1px solid var(--bf-line);border-radius:22px;padding:18px 20px;box-shadow:0 14px 34px rgba(15,23,42,.06);display:flex;align-items:center;justify-content:space-between;min-height:116px;}
    .bf-kpi-label{font-size:13px;color:#334155;font-weight:800;margin-bottom:8px;}
    .bf-kpi-value{font-size:27px;font-weight:950;color:var(--bf-navy);letter-spacing:-.03em;}
    .bf-kpi-delta{font-size:13px;font-weight:900;margin-top:7px;}
    .bf-icon{width:54px;height:54px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:25px;background:#EFF6FF;color:#1455D9;}
    .bf-icon.green{background:#EAF8F0;color:#16A34A}.bf-icon.purple{background:#F4F0FF;color:#7C3AED}.bf-icon.gold{background:#FFF7E6;color:#E5A400}
    .bf-card{border:1px solid var(--bf-line);border-radius:24px;background:white;box-shadow:0 14px 34px rgba(15,23,42,.06);padding:20px;margin-bottom:16px;}
    .good{color:var(--bf-green);font-weight:900}.bad{color:var(--bf-red);font-weight:900}
    .stButton>button{border-radius:14px!important;font-weight:900!important;border:1px solid #D9E3F0!important;min-height:44px;}
    .stButton>button[kind="primary"]{background:linear-gradient(135deg,#1455D9,#0B3EA8)!important;border:0!important;color:white!important;box-shadow:0 12px 24px rgba(20,85,217,.22)!important;}
    .stDataFrame{border-radius:18px;overflow:hidden;border:1px solid var(--bf-line)}
    div[data-testid="stMetric"]{background:white;border:1px solid var(--bf-line);border-radius:20px;padding:14px 16px;box-shadow:0 12px 30px rgba(15,23,42,.055)}
    div[data-testid="stMetricLabel"]{font-weight:800;color:#334155!important}
    div[data-testid="stMetricValue"]{color:var(--bf-navy)!important;font-weight:950!important}
    @media(max-width: 980px){.main .block-container{padding-left:.85rem;padding-right:.85rem}.bf-topbar{align-items:flex-start;flex-direction:column}.bf-logo{width:58px;height:58px;border-radius:18px;font-size:30px}.bf-title{font-size:34px}.bf-status{justify-content:flex-start;gap:10px}.bf-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.bf-kpi{padding:14px;min-height:98px;border-radius:18px}.bf-kpi-value{font-size:22px}.bf-icon{width:42px;height:42px;border-radius:13px;font-size:21px}}
    @media(max-width: 560px){.bf-kpi-grid{grid-template-columns:1fr 1fr}.bf-title{font-size:29px}.bf-subtitle{font-size:13px}.bf-pill,.bf-version{font-size:12px;padding:7px 10px}[data-testid="stSidebar"]{width:15rem!important}}

    .bf-logo-svg{display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 14px 25px rgba(20,85,217,.18));}
    .bf-logo-svg svg{display:block;border-radius:22px;}
    .bf-hero-badges{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;}
    .bf-hero-badge{background:#F3F7FF;border:1px solid #DDEAFF;color:#0B3EA8;border-radius:999px;padding:7px 10px;font-weight:850;font-size:12px;}
    .bf-title{background:linear-gradient(90deg,#071A3A 0%,#1455D9 74%);-webkit-background-clip:text;background-clip:text;color:transparent!important;}
    .bf-title span{color:inherit!important;}
    .bf-kpi{transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;}
    .bf-kpi:hover{transform:translateY(-3px);box-shadow:0 18px 42px rgba(20,85,217,.12);border-color:#CFE0FF;}
    .bf-card{transition:transform .18s ease, box-shadow .18s ease;}
    .bf-card:hover{transform:translateY(-2px);box-shadow:0 18px 42px rgba(15,23,42,.08);}
    [data-testid="stSidebar"]{min-width:248px;}
    [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{display:none!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label{border-radius:14px!important;padding:.72rem .85rem!important;margin:.20rem 0!important;border:1px solid transparent!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label p{font-weight:850!important;font-size:15px!important;}
    [data-testid="stSidebar"] [aria-checked="true"]{background:linear-gradient(135deg,#1455D9,#0B3EA8)!important;border-radius:14px!important;box-shadow:0 14px 28px rgba(20,85,217,.18)!important;}
    .bf-mobile-bottom{display:none;}
    @media(max-width: 760px){
      [data-testid="stSidebar"]{display:none!important;}
      .main .block-container{padding-top:.75rem!important;padding-bottom:5rem!important;}
      .bf-mobile-bottom{display:flex;position:fixed;left:10px;right:10px;bottom:10px;background:white;border:1px solid #E5EAF2;border-radius:22px;box-shadow:0 12px 30px rgba(15,23,42,.16);z-index:9999;justify-content:space-around;padding:8px 6px;}
      .bf-mobile-bottom span{font-size:11px;font-weight:800;color:#0F172A;text-align:center;line-height:1.15;}
      .bf-mobile-bottom b{font-size:18px;display:block;margin-bottom:2px;color:#1455D9;}
    }


    /* V7.1 visual polish */
    [data-testid="stSidebar"] [role="radiogroup"] label p{font-size:17px!important;font-weight:900!important;letter-spacing:-.01em!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label{padding:.86rem .95rem!important;margin:.28rem 0!important;}
    .bf-sidebar-title{font-size:20px!important;}
    .bf-sidebar-sub{font-size:13px!important;}
    .bf-topbar{background:linear-gradient(135deg,#FFFFFF 0%,#F7FAFF 100%);border:1px solid #E5EAF2;border-radius:28px;padding:22px 24px;box-shadow:0 18px 45px rgba(15,23,42,.055);margin:2px 0 18px 0;}
    .bf-brand{gap:18px;}
    .bf-logo-svg svg{border-radius:24px;}
    .bf-subtitle{font-size:16px;}
    .bf-status{gap:10px;align-items:center;}
    .bf-pill{padding:10px 13px;font-size:13px;box-shadow:none;background:#FFFFFF;}
    .bf-version{padding:10px 13px;font-size:13px;box-shadow:none;}
    .bf-kpi-grid{margin-top:12px;}
    .bf-kpi{min-height:104px;padding:16px 18px;}
    .bf-kpi-value{font-size:25px;line-height:1.15;}
    .bf-kpi-delta{font-size:12px;}
    @media(max-width:980px){.bf-topbar{padding:18px}.bf-status{width:100%;justify-content:flex-start}.bf-kpi-value{font-size:21px}}


    /* V7.2 sidebar market polish */
    [data-testid="stSidebar"] [role="radiogroup"] label{
      background:#F3F7FF!important;
      border:1px solid #DCEBFF!important;
      border-radius:16px!important;
      padding:.95rem 1rem!important;
      margin:.35rem 0!important;
      box-shadow:0 8px 18px rgba(20,85,217,.045)!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#EAF3FF!important;border-color:#CFE0FF!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label p{font-size:17px!important;font-weight:950!important;}
    [data-testid="stSidebar"] [aria-checked="true"]{background:linear-gradient(135deg,#1455D9,#0B3EA8)!important;border-color:#1455D9!important;}
    [data-testid="stSidebar"] [aria-checked="true"] p{color:white!important;}
    .bf-side-sep{height:1px;background:#E5EAF2;margin:1.05rem 0 .9rem 0;}
    .bf-market-title{font-size:13px;font-weight:950;color:#0F172A;margin:.25rem 0 .45rem 0;letter-spacing:.01em;}
    .bf-market-card{background:linear-gradient(135deg,#F8FBFF,#EEF6FF);border:1px solid #DCEBFF;border-radius:15px;padding:10px 12px;margin:7px 0;display:flex;align-items:center;justify-content:space-between;gap:10px;}
    .bf-market-name{font-size:12px;font-weight:900;color:#334155;}
    .bf-market-val{font-size:13px;font-weight:950;color:#0B3EA8;text-align:right;}
    .bf-market-note{font-size:10.5px;color:#64748B;line-height:1.2;margin-top:6px;}
    .stButton>button[kind="primary"]{background:linear-gradient(135deg,#C2410C,#9A3412)!important;border:0!important;color:white!important;box-shadow:0 12px 24px rgba(194,65,12,.22)!important;}



    /* V7.3 premium navy sidebar */
    [data-testid="stSidebar"]{
      background:linear-gradient(180deg,#061533 0%,#071A3A 48%,#041126 100%)!important;
      border-right:0!important;
      box-shadow:18px 0 45px rgba(4,17,38,.16)!important;
    }
    [data-testid="stSidebar"] *{color:#FFFFFF!important;}
    [data-testid="stSidebar"] [role="radiogroup"]{display:flex!important;flex-direction:column!important;gap:10px!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label{
      width:100%!important;
      min-height:58px!important;
      height:58px!important;
      box-sizing:border-box!important;
      display:flex!important;
      align-items:center!important;
      background:rgba(255,255,255,.075)!important;
      border:1px solid rgba(255,255,255,.15)!important;
      border-radius:16px!important;
      padding:0 16px!important;
      margin:0!important;
      box-shadow:none!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{
      background:rgba(37,99,235,.24)!important;
      border-color:rgba(96,165,250,.45)!important;
      transform:translateY(-1px);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label p{
      font-size:18px!important;
      font-weight:950!important;
      color:#FFFFFF!important;
      letter-spacing:-.01em!important;
    }
    [data-testid="stSidebar"] [aria-checked="true"]{
      background:linear-gradient(135deg,#1455D9,#0B3EA8)!important;
      border-color:rgba(96,165,250,.70)!important;
      box-shadow:0 14px 28px rgba(20,85,217,.26)!important;
    }
    .bf-sidebar-brand{padding:1.0rem .1rem 1.2rem .1rem!important;}
    .bf-sidebar-title{color:#FFFFFF!important;font-size:22px!important;}
    .bf-sidebar-sub{color:#93C5FD!important;font-size:13px!important;}
    .bf-side-sep{height:1px;background:rgba(255,255,255,.22)!important;margin:1.25rem 0 1rem 0!important;}
    .bf-market-title{font-size:13px!important;font-weight:950!important;color:#EAF3FF!important;display:flex;align-items:center;justify-content:space-between;text-transform:uppercase;letter-spacing:.04em;}
    .bf-market-title span{font-size:11px!important;color:#86EFAC!important;text-transform:none;letter-spacing:0;}
    .bf-market-card{
      background:rgba(255,255,255,.075)!important;
      border:1px solid rgba(255,255,255,.15)!important;
      border-radius:16px!important;
      padding:10px 12px!important;
      margin:8px 0!important;
      box-shadow:none!important;
    }
    .bf-market-name{font-size:12px!important;font-weight:900!important;color:#DBEAFE!important;}
    .bf-market-right{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:2px;}
    .bf-market-val{font-size:15px!important;font-weight:950!important;color:#FFFFFF!important;}
    .bf-market-pct{font-size:11px!important;font-weight:950!important;}
    .bf-market-pct.good{color:#4ADE80!important;}.bf-market-pct.bad{color:#FB7185!important;}.bf-market-pct.neutral{color:#CBD5E1!important;}
    .bf-market-note{font-size:10.5px!important;color:#BFDBFE!important;line-height:1.25;margin-top:8px!important;}
    .bf-logo-svg{filter:drop-shadow(0 14px 25px rgba(37,99,235,.20));}



    /* V7.4 Hawaiian Ocean sidebar refinement */
    :root{--bf-ocean:#008DB9;--bf-ocean-dark:#006B93;--bf-ocean-light:#17B6D2;}
    [data-testid="stSidebar"]{
      background:linear-gradient(180deg,#008DB9 0%,#0087B0 48%,#006B93 100%)!important;
      border-right:0!important;
      box-shadow:18px 0 45px rgba(0,107,147,.18)!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"]{gap:10px!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label,
    .bf-market-card{
      width:100%!important;
      height:64px!important;
      min-height:64px!important;
      box-sizing:border-box!important;
      border-radius:16px!important;
      background:rgba(255,255,255,.10)!important;
      border:1px solid rgba(255,255,255,.42)!important;
      box-shadow:0 12px 22px rgba(0,78,112,.08)!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label{
      display:flex!important;
      align-items:center!important;
      padding:0 18px!important;
      margin:0!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{
      background:rgba(255,255,255,.18)!important;
      border-color:rgba(255,255,255,.70)!important;
      transform:translateY(-1px);
    }
    [data-testid="stSidebar"] [aria-checked="true"]{
      background:rgba(255,255,255,.22)!important;
      border-color:rgba(255,255,255,.85)!important;
      box-shadow:0 14px 30px rgba(0,66,96,.18)!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label p{
      font-size:20px!important;
      font-weight:500!important;
      color:#FFFFFF!important;
      letter-spacing:-.01em!important;
    }
    .bf-sidebar-title{font-size:25px!important;font-weight:700!important;color:#FFFFFF!important;}
    .bf-sidebar-sub{font-size:15px!important;font-weight:400!important;color:#E0F7FF!important;}
    .bf-side-sep{background:rgba(255,255,255,.55)!important;margin:1.2rem 0 1rem 0!important;}
    .bf-market-title{
      font-size:17px!important;
      font-weight:500!important;
      color:#FFFFFF!important;
      text-transform:uppercase;
      letter-spacing:.02em!important;
      margin-bottom:10px!important;
    }
    .bf-market-title span{font-size:13px!important;font-weight:400!important;color:#D6FFEA!important;}
    .bf-market-card{
      display:flex!important;
      align-items:center!important;
      justify-content:space-between!important;
      padding:10px 13px!important;
      margin:8px 0!important;
    }
    .bf-market-name{font-size:15px!important;font-weight:400!important;color:#FFFFFF!important;line-height:1.15!important;}
    .bf-market-right{display:flex!important;flex-direction:column!important;align-items:flex-end!important;justify-content:center!important;gap:2px!important;}
    .bf-market-val{font-size:21px!important;font-weight:500!important;color:#FFFFFF!important;line-height:1.05!important;}
    .bf-market-pct{font-size:14px!important;font-weight:400!important;line-height:1.05!important;}
    .bf-market-pct.good{color:#D8FF80!important;}.bf-market-pct.bad{color:#FFE0E0!important;}.bf-market-pct.neutral{color:#E0F7FF!important;}
    .bf-market-note{font-size:12px!important;font-weight:400!important;color:#E0F7FF!important;}
    .bf-logo-svg{filter:drop-shadow(0 16px 26px rgba(0,107,147,.20));}
    .stButton>button[kind="primary"]{background:linear-gradient(135deg,#C2410C,#9A3412)!important;border:0!important;color:white!important;box-shadow:0 12px 24px rgba(194,65,12,.22)!important;}

    

    /* V7.6 Premium UI refinement: exact wide Hawaiian sidebar + cleaner home */
    :root{
      --bf-ocean:#008DB9;
      --bf-ocean-deep:#00769D;
      --bf-ocean-dark:#005F82;
      --bf-blue:#1455D9;
      --bf-navy:#071A3A;
      --bf-card-border:#E3EAF4;
    }
    .main .block-container{max-width:1320px!important;padding-left:2.0rem!important;padding-right:2.0rem!important;}
    section[data-testid="stSidebar"]{width:356px!important;min-width:356px!important;background:linear-gradient(180deg,#0098BF 0%,#008DB9 46%,#00769D 100%)!important;}
    section[data-testid="stSidebar"] > div{width:356px!important;min-width:356px!important;background:transparent!important;}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"]{gap:.72rem!important;}
    [data-testid="stSidebar"] .block-container,
    [data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-left:1.28rem!important;padding-right:1.28rem!important;}
    .bf-sidebar-brand{display:flex!important;align-items:center!important;gap:14px!important;padding:1.35rem .25rem 1.65rem .25rem!important;}
    .bf-sidebar-brand .bf-logo-svg{width:58px!important;height:58px!important;}
    .bf-sidebar-title{font-size:26px!important;font-weight:700!important;line-height:1.05!important;color:#fff!important;}
    .bf-sidebar-sub{font-size:15px!important;font-weight:400!important;color:#E6FAFF!important;margin-top:6px!important;}
    [data-testid="stSidebar"] [role="radiogroup"]{display:flex!important;flex-direction:column!important;gap:12px!important;width:100%!important;}
    [data-testid="stSidebar"] [role="radiogroup"] label{
      width:100%!important;
      height:76px!important;
      min-height:76px!important;
      max-height:76px!important;
      box-sizing:border-box!important;
      display:flex!important;
      align-items:center!important;
      justify-content:flex-start!important;
      padding:0 22px!important;
      margin:0!important;
      border-radius:17px!important;
      background:rgba(255,255,255,.105)!important;
      border:1px solid rgba(255,255,255,.48)!important;
      box-shadow:0 14px 28px rgba(0,77,112,.10)!important;
      transition:all .18s ease!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{
      background:rgba(255,255,255,.18)!important;
      border-color:rgba(255,255,255,.78)!important;
      transform:translateY(-1px)!important;
      box-shadow:0 18px 34px rgba(0,77,112,.16)!important;
    }
    [data-testid="stSidebar"] [aria-checked="true"]{
      background:rgba(255,255,255,.21)!important;
      border-color:rgba(255,255,255,.92)!important;
      box-shadow:0 18px 36px rgba(0,77,112,.18)!important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label p{
      font-size:22px!important;
      font-weight:400!important;
      letter-spacing:-.015em!important;
      color:#fff!important;
      line-height:1!important;
    }
    .bf-side-sep{height:1px!important;background:rgba(255,255,255,.60)!important;margin:1.45rem 0 1.1rem 0!important;}
    .bf-market-title{font-size:19px!important;font-weight:400!important;color:#fff!important;letter-spacing:.01em!important;margin-bottom:12px!important;}
    .bf-market-title span{font-size:14px!important;font-weight:400!important;color:#DAFFEA!important;}
    .bf-market-card{
      width:100%!important;
      height:76px!important;
      min-height:76px!important;
      max-height:76px!important;
      box-sizing:border-box!important;
      display:flex!important;
      align-items:center!important;
      justify-content:space-between!important;
      padding:12px 18px!important;
      margin:12px 0!important;
      border-radius:17px!important;
      background:rgba(255,255,255,.105)!important;
      border:1px solid rgba(255,255,255,.48)!important;
      box-shadow:0 14px 28px rgba(0,77,112,.10)!important;
    }
    .bf-market-name{font-size:17px!important;font-weight:400!important;color:#fff!important;line-height:1.1!important;}
    .bf-market-val{font-size:23px!important;font-weight:500!important;color:#fff!important;line-height:1.05!important;}
    .bf-market-pct{font-size:15px!important;font-weight:400!important;line-height:1!important;}
    .bf-market-note{font-size:13px!important;font-weight:400!important;color:#E8FBFF!important;line-height:1.35!important;margin-top:16px!important;}
    .bf-topbar{background:white!important;border:1px solid var(--bf-card-border)!important;border-radius:28px!important;padding:24px 28px!important;box-shadow:0 18px 46px rgba(15,23,42,.055)!important;margin:0 0 22px 0!important;}
    .bf-logo-svg svg{border-radius:22px!important;}
    .bf-title{font-size:42px!important;font-weight:800!important;letter-spacing:-.04em!important;}
    .bf-subtitle{font-size:16px!important;font-weight:500!important;color:#334155!important;}
    .bf-status{gap:12px!important;}
    .bf-pill,.bf-version{min-height:52px!important;display:flex!important;align-items:center!important;justify-content:center!important;text-align:center!important;border-radius:22px!important;padding:10px 18px!important;box-shadow:0 10px 28px rgba(15,23,42,.055)!important;font-weight:650!important;}
    .bf-kpi-grid{gap:16px!important;margin-top:18px!important;margin-bottom:20px!important;}
    .bf-kpi{min-height:136px!important;border-radius:22px!important;padding:22px 24px!important;}
    .bf-kpi-label{font-size:14px!important;font-weight:700!important;color:#334155!important;}
    .bf-kpi-value{font-size:30px!important;font-weight:850!important;line-height:1.15!important;}
    .bf-kpi-delta{font-size:13px!important;font-weight:700!important;}
    .bf-icon{width:48px!important;height:48px!important;border-radius:15px!important;font-size:21px!important;}
    .bf-refresh-banner{display:flex;align-items:center;justify-content:space-between;gap:18px;border:1px solid #D9E6F5;border-radius:17px;background:#FFFFFF;padding:15px 20px;margin:16px 0 24px 0;box-shadow:0 12px 30px rgba(15,23,42,.04);}
    .bf-refresh-left{display:flex;align-items:center;gap:13px;font-weight:700;color:#071A3A;}
    .bf-refresh-icon{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#EA580C;color:white;font-size:22px;box-shadow:0 10px 24px rgba(234,88,12,.22);}
    .bf-section-title{font-size:26px!important;font-weight:800!important;letter-spacing:-.03em;color:#071A3A;margin:8px 0 16px;}
    .bf-mini-card{background:white;border:1px solid var(--bf-card-border);border-radius:22px;padding:20px;box-shadow:0 14px 34px rgba(15,23,42,.05);margin-bottom:16px;}
    .bf-mini-label{font-size:13px;font-weight:650;color:#475569;margin-bottom:7px;}
    .bf-mini-value{font-size:28px;font-weight:850;letter-spacing:-.03em;color:#071A3A;line-height:1.1;}
    .bf-card-title{font-size:18px;font-weight:750;color:#071A3A;margin-bottom:12px;}
    .bf-winner{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #E8EEF7;padding:12px 0;}
    .bf-winner:last-child{border-bottom:none;}
    .bf-rank{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#F1F5F9;color:#0F172A;font-weight:750;}
    .bf-rank.gold{background:#FDE68A;color:#92400E}.bf-rank.silver{background:#E5E7EB;color:#374151}.bf-rank.bronze{background:#FDBA74;color:#7C2D12}
    .bf-winner-name{font-weight:700;color:#071A3A;}.bf-winner-sub{font-size:12px;color:#64748B;}
    .bf-quick-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-top:6px;}
    .bf-quick-card{background:white;border:1px solid var(--bf-card-border);border-radius:18px;padding:18px 14px;text-align:center;box-shadow:0 12px 30px rgba(15,23,42,.045);}
    .bf-quick-ico{font-size:30px;margin-bottom:8px}.bf-quick-title{font-weight:750;color:#071A3A}.bf-quick-sub{font-size:12px;color:#64748B;margin-top:4px;line-height:1.25;}
    .stButton>button[kind="primary"]{background:linear-gradient(135deg,#C2410C,#9A3412)!important;border:0!important;color:white!important;box-shadow:0 12px 24px rgba(194,65,12,.22)!important;}
    @media(max-width: 980px){section[data-testid="stSidebar"]{display:none!important}.main .block-container{padding-left:1rem!important;padding-right:1rem!important}.bf-topbar{padding:18px!important}.bf-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.bf-quick-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.bf-title{font-size:32px!important}.bf-status{justify-content:flex-start!important}.bf-pill,.bf-version{min-height:42px!important;font-size:12px!important}.bf-kpi{min-height:116px!important}.bf-kpi-value{font-size:23px!important}}
</style>
    """, unsafe_allow_html=True)


def render_brand_header(total, pl, pl_pct, realized, unrealized):
    now_txt = pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')
    logo = bf_logo_html(78)
    st.markdown(f'''
    <div class="bf-topbar">
      <div class="bf-brand">
        {logo}
        <div>
          <div class="bf-title">Benim <span>Finans</span></div>
          <div class="bf-subtitle">Akıllı yatırım takibi, net sonuçlar.</div>
        </div>
      </div>
      <div class="bf-status">
        <div class="bf-pill"><span class="bf-dot"></span>Sistem aktif</div>
        <div class="bf-pill">Son güncelleme<br><b>{now_txt}</b></div>
        <div class="bf-version">MyFin v7.6</div>
      </div>
    </div>
    <div class="bf-kpi-grid">
      <div class="bf-kpi"><div><div class="bf-kpi-label">Toplam Portföy</div><div class="bf-kpi-value">{tl(total)}</div><div class="bf-kpi-delta {'good' if pl>=0 else 'bad'}">{pct(pl_pct)} · {tl(pl)}</div></div><div class="bf-icon">💼</div></div>
      <div class="bf-kpi"><div><div class="bf-kpi-label">Toplam Yatırım</div><div class="bf-kpi-value">{tl(max(total-pl,0))}</div><div class="bf-kpi-delta">Maliyet bazlı</div></div><div class="bf-icon gold">🪙</div></div>
      <div class="bf-kpi"><div><div class="bf-kpi-label">Bekleyen Kâr</div><div class="bf-kpi-value {'good' if unrealized>=0 else 'bad'}">{tl(unrealized)}</div><div class="bf-kpi-delta {'good' if unrealized>=0 else 'bad'}">Portföyde bekleyen</div></div><div class="bf-icon green">↗</div></div>
      <div class="bf-kpi"><div><div class="bf-kpi-label">Satış Kârı</div><div class="bf-kpi-value {'good' if realized>=0 else 'bad'}">{tl(realized)}</div><div class="bf-kpi-delta">Kesinleşen sonuç</div></div><div class="bf-icon purple">▮</div></div>
    </div>
    <div class="bf-mobile-bottom">
      <span><b>⌂</b>Ana</span><span><b>💼</b>Portföy</span><span><b>＋</b>Varlık</span><span><b>▤</b>İşlem</span><span><b>⚙</b>Ayarlar</span>
    </div>
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


def _market_price_value(symbol, category, manual=0):
    try:
        price, source = get_price_try(symbol, category, manual)
        return float(price or 0), source
    except Exception:
        return 0.0, "-"


@st.cache_data(ttl=900, show_spinner=False)
def _yahoo_now_prev(ysym):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range=5d&interval=1d"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=6)
        r.raise_for_status()
        data = r.json()["chart"]["result"][0]
        closes = [x for x in data["indicators"]["quote"][0].get("close", []) if x is not None]
        now = data.get("meta", {}).get("regularMarketPrice") or (closes[-1] if closes else None)
        prev = closes[-2] if len(closes) >= 2 else None
        if now is None or prev in (None, 0):
            return None, None, None
        pct_change = (float(now) - float(prev)) / float(prev) * 100
        return float(now), float(prev), pct_change
    except Exception:
        return None, None, None


def _market_quote(symbol, category):
    price, _ = _market_price_value(symbol, category)
    pct_change = None
    try:
        if symbol == 'USDTRY':
            _, _, pct_change = _yahoo_now_prev('USDTRY=X')
        elif symbol == 'EURTRY':
            _, _, pct_change = _yahoo_now_prev('EURTRY=X')
        elif symbol == 'GRAM_ALTIN':
            gc_now, gc_prev, _ = _yahoo_now_prev('GC=F')
            usd_now, usd_prev, _ = _yahoo_now_prev('USDTRY=X')
            if gc_now and gc_prev and usd_now and usd_prev:
                gram_now = gc_now * usd_now / 31.1034768
                gram_prev = gc_prev * usd_prev / 31.1034768
                pct_change = (gram_now - gram_prev) / gram_prev * 100 if gram_prev else None
    except Exception:
        pct_change = None
    return price, pct_change


def _pct_badge(pct_value):
    if pct_value is None:
        return "<span class='bf-market-pct neutral'>—</span>"
    cls = 'good' if pct_value >= 0 else 'bad'
    arrow = '↗' if pct_value >= 0 else '↘'
    return f"<span class='bf-market-pct {cls}'>{arrow} {pct(pct_value)}</span>"


def render_sidebar_market_prices():
    usd, usd_pct = _market_quote('USDTRY', 'Döviz')
    eur, eur_pct = _market_quote('EURTRY', 'Döviz')
    gram, gram_pct = _market_quote('GRAM_ALTIN', 'Altın')

    # Yaklaşık fiziki altın hesapları. Kuyumcu makası/darphane primleri dahil değildir.
    rows = [
        ('💵 Dolar', usd, usd_pct),
        ('💶 Euro', eur, eur_pct),
        ('🥇 Gram Altın', gram, gram_pct),
        ('🪙 Çeyrek Altın', gram * 1.754 if gram else 0, gram_pct),
        ('🟡 Tam Altın', gram * 7.016 if gram else 0, gram_pct),
        ('🏛️ Cumhuriyet', gram * 7.216 if gram else 0, gram_pct),
    ]
    html = "<div class='bf-side-sep'></div><div class='bf-market-title'>Canlı Piyasa <span>● Canlı</span></div>"
    for name, val, pct_val in rows:
        value = tl(val) if val else '-'
        html += f"<div class='bf-market-card'><div class='bf-market-name'>{name}</div><div class='bf-market-right'>{_pct_badge(pct_val)}<div class='bf-market-val'>{value}</div></div></div>"
    html += "<div class='bf-market-note'>Yüzdeler yaklaşık günlük değişimdir. Fiziki altınlarda kuyumcu alış/satış farkı dahil değildir.</div>"
    st.markdown(html, unsafe_allow_html=True)


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
    st.markdown(f"<div class='bf-sidebar-brand'>{bf_logo_html(42)}<div><div class='bf-sidebar-title'>Benim Finans</div><div class='bf-sidebar-sub'>MyFin v7.6</div></div></div>", unsafe_allow_html=True)
    page=st.radio('Menü', ['🏠 Ana Sayfa','💼 Portföy','➕ Varlık Ekle','📒 İşlem Defteri','📊 Analiz','⚙️ Ayarlar'], label_visibility='collapsed')
    render_sidebar_market_prices()

portfolio=build_portfolio()
cat=category_summary()
total=float(portfolio['Güncel Değer TL'].sum()) if not portfolio.empty else 0
pl=float(portfolio['Toplam K/Z TL'].sum()) if not portfolio.empty else 0
base=total-pl
pl_pct=(pl/base*100) if base else 0
realized=float(portfolio['Gerçekleşmiş K/Z TL'].sum()) if not portfolio.empty else 0
unrealized=float(portfolio['Gerçekleşmemiş K/Z TL'].sum()) if not portfolio.empty else 0

render_brand_header(total, pl, pl_pct, realized, unrealized)

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
    if cat.empty:
        st.info('Portföy boş. ➕ Varlık Ekle ekranından geçmiş tarihli ilk alımlarını girerek başlayabilirsin.')
    else:
        st.markdown("<div class='bf-refresh-banner'><div class='bf-refresh-left'><div class='bf-refresh-icon'>↻</div><div>Fiyatlar anlık olarak güncellenmektedir.</div></div><div style='color:#334155;font-weight:500'>Canlı veriler ile portföyünüz güncel tutulur.</div></div>", unsafe_allow_html=True)

        left, right = st.columns([1.05, 1])
        with left:
            st.markdown("<div class='bf-card-title'>Portföy Dağılımı</div>", unsafe_allow_html=True)
            fig = px.pie(cat, values='Güncel Değer TL', names='Kategori', hole=.58)
            fig.update_traces(textposition='outside', textinfo='none')
            fig.update_layout(
                height=390,
                margin=dict(l=0, r=0, t=10, b=10),
                legend=dict(orientation='v', yanchor='middle', y=.5, xanchor='left', x=.82),
                annotations=[dict(text=f"<b>{tl(total)}</b><br><span style='font-size:12px'>Toplam Portföy</span>", x=.5, y=.5, showarrow=False, font_size=16)]
            )
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.markdown("<div class='bf-card-title'>Portföy Değeri <span style='font-size:13px;font-weight:500;color:#64748B'>(30 Gün)</span></div>", unsafe_allow_html=True)
            snaps = snapshots_df()
            if not snaps.empty:
                fig2 = px.line(snaps.tail(30), x='snapshot_date', y='total_value_try', markers=False)
                fig2.update_layout(height=390, margin=dict(l=0,r=0,t=10,b=10), showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.markdown("<div class='bf-mini-card' style='height:340px;display:flex;align-items:center;justify-content:center;color:#64748B'>Portföy geçmişi için günlük değer kaydı oluştur.</div>", unsafe_allow_html=True)

        c1, c2 = st.columns([1.45, .95])
        with c1:
            st.markdown("<div class='bf-card-title'>Varlık Kategori Özeti</div>", unsafe_allow_html=True)
            cat_show = cat.copy()
            if 'Kalan Maliyet TL' in cat_show.columns:
                cat_show['Getiri %'] = cat_show.apply(lambda r: (float(r.get('Toplam K/Z TL', 0)) / float(r.get('Kalan Maliyet TL', 0)) * 100) if float(r.get('Kalan Maliyet TL', 0) or 0) else 0, axis=1)
            cols_to_show = [c for c in ['Kategori','Güncel Değer TL','Kalan Maliyet TL','Toplam K/Z TL','Getiri %'] if c in cat_show.columns]
            st.dataframe(money_cols(cat_show[cols_to_show], ['Güncel Değer TL','Kalan Maliyet TL','Toplam K/Z TL']), use_container_width=True, hide_index=True)
        with c2:
            st.markdown("<div class='bf-card-title'>En Çok Kazandıranlar</div>", unsafe_allow_html=True)
            top = portfolio.sort_values('Toplam K/Z TL', ascending=False).head(5)
            if top.empty:
                st.info('Henüz veri yok.')
            else:
                html = "<div class='bf-mini-card'>"
                for i, (_, r) in enumerate(top.iterrows(), start=1):
                    rank_cls = 'gold' if i == 1 else 'silver' if i == 2 else 'bronze' if i == 3 else ''
                    val = float(r.get('Toplam K/Z TL', 0) or 0)
                    getiri = float(r.get('Getiri %', 0) or 0)
                    html += f"<div class='bf-winner'><div style='display:flex;align-items:center;gap:12px'><div class='bf-rank {rank_cls}'>{i}</div><div><div class='bf-winner-name'>{r.get('Varlık','-')}</div><div class='bf-winner-sub'>{r.get('Kategori','')}</div></div></div><div style='text-align:right'><div class='{ 'good' if val>=0 else 'bad' }'>{pct(getiri)}</div><div class='{ 'good' if val>=0 else 'bad' }'>{tl(val)}</div></div></div>"
                html += "</div>"
                st.markdown(html, unsafe_allow_html=True)

        st.markdown("<div class='bf-section-title'>Hızlı İşlemler</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='bf-quick-grid'>
          <div class='bf-quick-card'><div class='bf-quick-ico'>➕</div><div class='bf-quick-title'>Varlık Ekle</div><div class='bf-quick-sub'>Portföyünüze yeni varlık ekleyin</div></div>
          <div class='bf-quick-card'><div class='bf-quick-ico'>🛒</div><div class='bf-quick-title'>Alış İşlemi</div><div class='bf-quick-sub'>Hisse, altın, döviz alışı yapın</div></div>
          <div class='bf-quick-card'><div class='bf-quick-ico'>📈</div><div class='bf-quick-title'>Satış İşlemi</div><div class='bf-quick-sub'>Varlıklarınızı satışa çıkarın</div></div>
          <div class='bf-quick-card'><div class='bf-quick-ico'>📒</div><div class='bf-quick-title'>İşlem Defteri</div><div class='bf-quick-sub'>Tüm işlemlerinizi görüntüleyin</div></div>
          <div class='bf-quick-card'><div class='bf-quick-ico'>⚙️</div><div class='bf-quick-title'>Ayarlar</div><div class='bf-quick-sub'>Uygulama ayarlarını düzenleyin</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.info('Portföy verileriniz Supabase ile güvenli şekilde senkronize edilir ve gerçek zamanlı güncellenir.')

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

elif page=='➕ Varlık Ekle':
    st.header('🛒 İlk Alış / Geçmiş Tarihli Alış')

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

    # Kategori ve varlık alanları formun dışında olmalı.
    # Streamlit formlarında seçim değişince ekran anında yenilenmez;
    # bu yüzden ABD Hisse seçilse bile eski TL alanları görünüyordu.
    c1, c2 = st.columns(2)
    with c1:
        kategori = st.selectbox(
            'Kategori',
            ['Altın','Döviz','BIST Hisse','ABD Hisse','Kripto','Fon','BES','Diğer'],
            key='new_kategori'
        )
    with c2:
        emtia = st.text_input(
            'Emtia / Varlık',
            placeholder='Gram Altın, Dolar, Euro, ASELS, RKLB',
            key='new_emtia'
        )

    abd_hisse = kategori == 'ABD Hisse'

    with st.form('new_asset'):
        c3, c4, c5 = st.columns(3)
        with c3:
            alis_tarihi = st.date_input('Alış tarihi', value=date.today())
        with c4:
            adet_txt = tr_amount_input('Adet / Gram', 'new_adet', '0,00')
            adet = parse_tr_number(adet_txt)
        with c5:
            if abd_hisse:
                para_birimi = st.selectbox('Alış para birimi', ['USD'], index=0, help='ABD hisselerinde alış fiyatı hisse başına USD girilir.')
            else:
                para_birimi = st.selectbox('Alış para birimi', ['TRY','USD','EUR'], index=0)

        bugun = date.today()
        eski_tarih = alis_tarihi < bugun

        if abd_hisse:
            st.info('ABD hissesi için fiyatları USD gir. TL karşılığını program USD/TRY kuru ile hesaplayacak.')
            c6, c7 = st.columns(2)
            with c6:
                alis_fiyati_txt = tr_amount_input(
                    'Alış fiyatı (USD)',
                    'new_alis_fiyati_usd',
                    '0,00',
                    help='Hisse başına USD alış fiyatı. Toplam TL tutarı buraya yazma.'
                )
                alis_fiyati_orijinal = parse_tr_number(alis_fiyati_txt)
            with c7:
                alis_kuru_txt = tr_amount_input(
                    'Alış günü USD/TRY kuru',
                    'new_alis_kuru_usdtry',
                    '0,00',
                    help='Alış yaptığın günkü dolar kuru. Örnek: 32,25'
                )
                kur = parse_tr_number(alis_kuru_txt)

            c8, c9 = st.columns(2)
            with c8:
                komisyon_txt = tr_amount_input('Komisyon TL', 'new_komisyon', '0,00', help='Alışta maliyete eklenir.')
                komisyon = parse_tr_number(komisyon_txt)
            with c9:
                guncel_usd_txt = tr_amount_input(
                    'Manuel güncel fiyat (USD)',
                    'new_manuel_fiyat_usd',
                    '0,00',
                    help='Güncel hisse fiyatını USD gir. Boş/0 bırakırsan otomatik fiyat kaynakları denenir.'
                )
                guncel_fiyat_usd = parse_tr_number(guncel_usd_txt)

            c10, c11 = st.columns(2)
            with c10:
                guncel_kur_txt = tr_amount_input(
                    'Güncel USD/TRY kuru',
                    'new_guncel_kur_usdtry',
                    '0,00',
                    help='Güncel manuel USD fiyatı girdiysen bugünkü dolar kurunu da gir.'
                )
                guncel_kur = parse_tr_number(guncel_kur_txt)
            with c11:
                not_alani = st.text_input('Not')

            alis_fiyati_tl_onizleme = alis_fiyati_orijinal * kur if alis_fiyati_orijinal > 0 and kur > 0 else 0
            manuel_fiyat = guncel_fiyat_usd * guncel_kur if guncel_fiyat_usd > 0 and guncel_kur > 0 else 0
            if alis_fiyati_tl_onizleme > 0:
                st.caption(f'Alış fiyatı TL önizleme: {alis_fiyati_tl_onizleme:,.2f} TL / adet')
            if manuel_fiyat > 0:
                st.caption(f'Manuel güncel fiyat TL önizleme: {manuel_fiyat:,.2f} TL / adet')

            kur_bilgisi = f'Alış kuru USD/TRY: {kur:.4f}' if kur > 0 else ''
            manuel_tl = 0.0
        else:
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
                if abd_hisse:
                    if kur <= 0:
                        st.error('ABD hissesi için alış günü USD/TRY kuru girilmeli.')
                        st.stop()
                    alis_fiyati_tl = alis_fiyati_orijinal * kur
                elif para_birimi == 'TRY':
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
                if abd_hisse:
                    if manuel_fiyat > 0:
                        detay_not = (detay_not + ' | ' if detay_not else '') + f'Alış: {alis_fiyati_orijinal} USD; Alış kuru: {kur:.4f}; TL fiyat: {alis_fiyati_tl:.2f}; Güncel manuel: {guncel_fiyat_usd} USD x {guncel_kur:.4f} = {manuel_fiyat:.2f} TL'
                    else:
                        detay_not = (detay_not + ' | ' if detay_not else '') + f'Alış: {alis_fiyati_orijinal} USD; Alış kuru: {kur:.4f}; TL fiyat: {alis_fiyati_tl:.2f}'
                elif para_birimi != 'TRY':
                    detay_not = (detay_not + ' | ' if detay_not else '') + f'Alış: {alis_fiyati_orijinal} {para_birimi}; TL fiyat: {alis_fiyati_tl:.2f}; {kur_bilgisi}'

                add_asset(emtia, sembol, kategori, manual_price_try=manuel_fiyat)
                add_transaction(alis_tarihi, sembol, 'Alış', adet, alis_fiyati_tl, komisyon, detay_not)
                st.success(f'{emtia} kaydedildi. Otomatik sembol: {sembol}. Alış fiyatı TL: {alis_fiyati_tl:,.2f}')
                st.rerun()

elif page=='📒 İşlem Defteri':
    st.header('📒 İşlem Defteri')
    st.info('Bu ekran, mevcut bir varlığa sonradan alış/satış/temettü/komisyon işlemi eklemek içindir. İlk alış için ➕ Varlık Ekle ekranını kullanabilirsin.')
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

elif page=='📊 Analiz':
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
    st.caption('Uygulama durumu, bağlantı testi, isim/kategori düzenleme ve güvenli temizlik işlemleri.')

    tab_durum, tab_duzen, tab_tehlike = st.tabs(['☁️ Sistem Durumu', '✏️ İsim & Kategori', '🧹 Temizlik'])

    with tab_durum:
        st.subheader('☁️ Veri altyapısı')
        st.info(f'Veri altyapısı: {backend_name()}')
        if using_supabase():
            st.success('Supabase aktif: Telefondan veya bilgisayardan yapılan değişiklikler bulutta kalıcı saklanır.')
        else:
            st.warning('Supabase secrets bulunamadı. Yerel geliştirme için SQLite kullanılıyor.')

        if st.button('🔌 Bağlantıyı test et', use_container_width=True):
            try:
                test_assets = assets_df(active_only=False, include_archived=True)
                st.success(f'Bağlantı başarılı. Kayıtlı varlık sayısı: {len(test_assets)}')
            except Exception as e:
                st.error(f'Bağlantı testi başarısız: {e}')

        st.subheader('ℹ️ Sürüm')
        st.write('Benim Finans • MyFin • V7.6 Premium UI')
        st.write('Bu sürümde Hawaiian Ocean premium sidebar, genişletilmiş menü kartları, modern ana sayfa kartları ve mobil uyumlu arayüz kullanılır.')

    with tab_duzen:
        st.subheader('✏️ Varlık adı, kategori ve manuel fiyat düzenle')
        assets_all = assets_df(active_only=False, include_archived=True)
        if assets_all.empty:
            st.info('Düzenlenecek varlık yok.')
        else:
            edit_cols = [c for c in ['name','symbol','category','manual_price_try','active','archived'] if c in assets_all.columns]
            edited = st.data_editor(
                assets_all[edit_cols],
                use_container_width=True,
                disabled=['symbol'],
                num_rows='fixed',
                key='settings_assets_editor'
            )
            if st.button('💾 Varlık ayarlarını kaydet', type='primary', use_container_width=True):
                for _, r in edited.iterrows():
                    update_asset(r['symbol'], r['name'], r['category'], r.get('manual_price_try', 0), r.get('active', True))
                    if bool(r.get('archived', False)):
                        archive_asset(r['symbol'])
                    else:
                        restore_asset(r['symbol'])
                st.success('Varlık ayarları kaydedildi.')
                st.rerun()

            st.divider()
            st.subheader('🏷️ Kategori başlığını toplu değiştir')
            categories = sorted([str(x) for x in assets_all['category'].dropna().unique().tolist()]) if 'category' in assets_all.columns else []
            if categories:
                old_cat = st.selectbox('Değiştirilecek kategori', categories)
                new_cat = st.text_input('Yeni kategori adı', value=old_cat)
                if st.button('🏷️ Kategoriyi toplu güncelle', use_container_width=True):
                    if not new_cat.strip():
                        st.error('Yeni kategori adı boş olamaz.')
                    else:
                        affected = assets_all[assets_all['category'].astype(str) == str(old_cat)]
                        for _, r in affected.iterrows():
                            update_asset(r['symbol'], r['name'], new_cat.strip(), r.get('manual_price_try', 0), r.get('active', True))
                        st.success(f'{old_cat} kategorisi {new_cat.strip()} olarak güncellendi.')
                        st.rerun()

            st.divider()
            st.subheader('🧭 Kategori önerileri')
            st.caption('Yeni girişlerde kullanılacak ana kategoriler: Altın, Döviz, BIST Hisse, ABD Hisse, Kripto, Fon, BES, Diğer. İstersen varlık düzenleme tablosundan özel kategori adı da verebilirsin.')

    with tab_tehlike:
        st.subheader('🧹 Tüm veriyi sıfırla')
        st.warning('Bu işlem portföyü, işlemleri ve fiyat önbelleğini siler. Supabase kullanıyorsan canlı veriyi etkiler.')

        admin_password = st.text_input(
            'Admin şifresi',
            type='password',
            placeholder='Admin şifresini gir',
            help='Güvenlik için toplu temizlik işlemlerinde admin şifresi gerekir.'
        )
        confirm = st.checkbox('Tüm portföyü, işlemleri ve fiyat önbelleğini silmeyi onaylıyorum')
        password_ok = admin_password == 'benimfinansadmin2026'

        if admin_password and not password_ok:
            st.error('Admin şifresi hatalı.')

        if st.button('🗑️ Tüm portföyü temizle', type='primary', disabled=not (confirm and password_ok)):
            clear_all_data()
            st.success('Portföy tamamen temizlendi.')
            st.rerun()
