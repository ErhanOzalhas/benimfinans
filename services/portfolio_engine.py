
import pandas as pd
from database.db import assets_df, transactions_df, price_cache_df

BUY_ACTIONS = {"Alış", "Açılış"}
SELL_ACTIONS = {"Satış"}
DIVIDEND_ACTIONS = {"Temettü"}
FEE_ACTIONS = {"Komisyon"}


def _safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def build_portfolio():
    assets = assets_df()
    tx = transactions_df()
    prices = price_cache_df()

    price_map = (
        dict(zip(prices.get("symbol", []), prices.get("price_try", [])))
        if not prices.empty
        else {}
    )

    out = []

    for _, a in assets.iterrows():
        sym = str(a["symbol"]).strip().upper()

        t = (
            tx[tx["asset_symbol"] == sym].sort_values(["tx_date", "id"])
            if not tx.empty and "asset_symbol" in tx.columns
            else pd.DataFrame()
        )

        qty = 0.0
        cost = 0.0
        realized = 0.0
        total_buys = 0.0
        total_sells = 0.0
        dividends = 0.0
        commissions = 0.0
        warnings = []

        for _, r in t.iterrows():
            action = str(r.get("action", "")).strip()
            q = _safe_float(r.get("quantity"))
            price = _safe_float(r.get("price_try"))
            comm = _safe_float(r.get("commission_try"))

            if action in BUY_ACTIONS:
                buy_cost = q * price + comm
                qty += q
                cost += buy_cost
                total_buys += buy_cost
                commissions += comm

            elif action in SELL_ACTIONS:
                if q <= 0:
                    continue

                if qty <= 0:
                    warnings.append("Elde varlık yokken satış")
                    proceeds = q * price - comm
                    realized += proceeds
                    total_sells += proceeds
                    commissions += comm
                    continue

                sell_qty = min(q, qty)

                if q > qty:
                    warnings.append(f"Fazla satış: {q - qty:.6f}")

                avg = cost / qty if qty else 0
                sold_cost = avg * sell_qty
                proceeds = sell_qty * price - comm

                realized += proceeds - sold_cost
                cost -= sold_cost
                qty -= sell_qty
                total_sells += proceeds
                commissions += comm

            elif action in DIVIDEND_ACTIONS:
                income = q * price - comm
                realized += income
                dividends += income
                commissions += comm

            elif action in FEE_ACTIONS:
                fee = comm if comm else q * price
                realized -= fee
                commissions += fee

        current_price = _safe_float(
            price_map.get(sym, a.get("manual_price_try", 0) or 0)
        )

        value = qty * current_price
        unrealized = value - cost
        avg_cost = cost / qty if qty else 0
        total_pl = realized + unrealized
        return_pct = (total_pl / total_buys * 100) if total_buys else 0

        out.append(
            {
                "Varlık": a.get("name", sym),
                "Sembol": sym,
                "Kategori": a.get("category", "Diğer"),
                "Miktar": qty,
                "Ort. Maliyet TL": avg_cost,
                "Kalan Maliyet TL": cost,
                "Güncel Fiyat TL": current_price,
                "Güncel Değer TL": value,
                "Gerçekleşmiş K/Z TL": realized,
                "Gerçekleşmemiş K/Z TL": unrealized,
                "Toplam K/Z TL": total_pl,
                "Getiri %": return_pct,
                "Toplam Alış TL": total_buys,
                "Toplam Satış TL": total_sells,
                "Temettü TL": dividends,
                "Komisyon TL": commissions,
                "Uyarı": " | ".join(warnings),
            }
        )

    return pd.DataFrame(out)


def category_summary():
    df = build_portfolio()
    if df.empty:
        return df

    return df.groupby("Kategori", as_index=False).agg(
        {
            "Güncel Değer TL": "sum",
            "Kalan Maliyet TL": "sum",
            "Gerçekleşmiş K/Z TL": "sum",
            "Gerçekleşmemiş K/Z TL": "sum",
            "Toplam K/Z TL": "sum",
            "Temettü TL": "sum",
            "Komisyon TL": "sum",
        }
    )


def date_range_analysis(start, end):
    tx = transactions_df()

    if tx.empty:
        return pd.DataFrame(), {
            "net_cash": 0,
            "buy_total": 0,
            "sell_total": 0,
            "dividend": 0,
            "commission": 0,
        }

    mask = (pd.to_datetime(tx["tx_date"]) >= pd.to_datetime(start)) & (
        pd.to_datetime(tx["tx_date"]) <= pd.to_datetime(end)
    )

    r = tx[mask].copy()

    if r.empty:
        return r, {
            "net_cash": 0,
            "buy_total": 0,
            "sell_total": 0,
            "dividend": 0,
            "commission": 0,
        }

    r["Tutar TL"] = r["quantity"].astype(float) * r["price_try"].astype(float)
    r["Komisyon TL"] = r["commission_try"].fillna(0).astype(float)

    buy = float(r[r["action"].isin(BUY_ACTIONS)]["Tutar TL"].sum())
    sell = float(r[r["action"].isin(SELL_ACTIONS)]["Tutar TL"].sum())
    div = float(r[r["action"].isin(DIVIDEND_ACTIONS)]["Tutar TL"].sum())
    comm = float(r["Komisyon TL"].sum())

    return r, {
        "net_cash": sell + div - buy - comm,
        "buy_total": buy,
        "sell_total": sell,
        "dividend": div,
        "commission": comm,
    }
