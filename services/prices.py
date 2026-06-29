from __future__ import annotations

import io
import time
from typing import Any

import pandas as pd
import requests
import streamlit as st


def _tr_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace("₺", "").replace("TL", "").replace("$", "")
    if s in ["", "-", "N/D", "nan", "None"]:
        return None
    try:
        # Turkish format: 4.312,20
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        return float(s)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def get_turkish_rates() -> dict[str, float]:
    """Döviz ve gram altın için ücretsiz kaynak. Başarısız olursa boş sözlük döner."""
    out: dict[str, float] = {}
    try:
        r = requests.get("https://finans.truncgil.com/today.json", timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        data = r.json()
        mapping = {
            "USDTRY": "ABD DOLARI",
            "EURTRY": "EURO",
            "GBPTRY": "İNGİLİZ STERLİNİ",
            "GRAM_ALTIN": "Gram Altın",
        }
        for sym, key in mapping.items():
            item = data.get(key) or {}
            val = item.get("Satış") or item.get("Alış")
            parsed = _tr_float(val)
            if parsed:
                out[sym] = parsed
    except Exception:
        pass
    return out


@st.cache_data(ttl=900, show_spinner=False)
def get_stooq_price(symbol: str) -> tuple[float | None, str]:
    s = symbol.upper().strip()
    candidates: list[str] = []
    if s.endswith(".US"):
        candidates.append(s.replace(".US", "").lower() + ".us")
    elif s.endswith(".IS"):
        candidates.append(s.replace(".IS", "").lower() + ".tr")
        candidates.append(s.replace(".IS", "").lower() + ".is")
    else:
        # BIST + US fallback
        candidates.extend([s.lower() + ".tr", s.lower() + ".is", s.lower() + ".us"])
    for c in candidates:
        try:
            url = f"https://stooq.com/q/l/?s={c}&f=sd2t2ohlcv&h&e=csv"
            txt = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"}).text
            df = pd.read_csv(io.StringIO(txt))
            if df.empty:
                continue
            close = df.iloc[0].get("Close")
            price = _tr_float(close)
            if price and price > 0:
                return price, f"Stooq:{c}"
        except Exception:
            continue
    return None, "Online fiyat alınamadı"


def enrich_prices(assets: pd.DataFrame) -> pd.DataFrame:
    rates = get_turkish_rates()
    usd_try = rates.get("USDTRY")
    rows = []
    for _, r in assets.iterrows():
        sym = str(r["symbol"]).upper().strip()
        cat = str(r["category"])
        manual = float(r.get("manual_price_try", 0) or 0)
        price: float | None = None
        source = "Fiyat yok"

        if sym in rates:
            price = rates[sym]
            source = "Online"
        elif cat in ["ABD Hisse", "BIST", "Kripto", "Fon", "Diğer"]:
            p, src = get_stooq_price(sym)
            if p:
                if cat == "ABD Hisse" and usd_try:
                    price = p * usd_try
                    source = src + " × USDTRY"
                else:
                    price = p
                    source = src
            else:
                source = src

        if (not price or price <= 0) and manual > 0:
            price = manual
            source = "Manuel fiyat"

        quantity = float(r.get("quantity", 0) or 0)
        cost = float(r.get("cost_try", 0) or 0)
        total = quantity * (price or 0)
        cost_total = quantity * cost
        pnl = total - cost_total if cost_total > 0 else 0
        pnl_pct = (pnl / cost_total * 100) if cost_total > 0 else 0
        rows.append({**r.to_dict(), "price_try": price or 0, "total_try": total, "pnl_try": pnl, "pnl_pct": pnl_pct, "source": source})
    return pd.DataFrame(rows)


def format_try(x: float) -> str:
    return f"{float(x):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
