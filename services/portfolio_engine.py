
import pandas as pd
from database.db import assets_df, transactions_df, price_cache_df

BUY_ACTIONS={'Alış','Açılış'}
SELL_ACTIONS={'Satış'}


def build_portfolio():
    assets=assets_df(); tx=transactions_df(); prices=price_cache_df()
    price_map=dict(zip(prices.get('symbol',[]), prices.get('price_try',[]))) if not prices.empty else {}
    out=[]
    for _,a in assets.iterrows():
        sym=a['symbol']; t=tx[tx['asset_symbol']==sym].sort_values(['tx_date','id']) if not tx.empty else pd.DataFrame()
        qty=0.0; cost=0.0; realized=0.0; total_buys=0.0; total_sells=0.0
        for _,r in t.iterrows():
            q=float(r['quantity']); price=float(r['price_try']); comm=float(r.get('commission_try',0) or 0)
            if r['action'] in BUY_ACTIONS:
                qty += q; cost += q*price + comm; total_buys += q*price + comm
            elif r['action'] in SELL_ACTIONS:
                if qty>0:
                    avg=cost/qty
                    sold_cost=avg*q
                    proceeds=q*price-comm
                    realized += proceeds-sold_cost
                    cost -= sold_cost; qty -= q; total_sells += proceeds
                else:
                    realized += q*price-comm; total_sells += q*price-comm
            elif r['action']=='Temettü':
                realized += q*price - comm
            elif r['action']=='Komisyon':
                realized -= comm or q*price
        current_price=float(price_map.get(sym, a.get('manual_price_try',0) or 0) or 0)
        value=qty*current_price
        unrealized=value-cost
        avg_cost=(cost/qty) if qty else 0
        out.append({
            'Varlık':a['name'],'Sembol':sym,'Kategori':a['category'],'Miktar':qty,
            'Ort. Maliyet TL':avg_cost,'Kalan Maliyet TL':cost,'Güncel Fiyat TL':current_price,
            'Güncel Değer TL':value,'Gerçekleşmiş K/Z TL':realized,'Gerçekleşmemiş K/Z TL':unrealized,
            'Toplam K/Z TL':realized+unrealized,'Getiri %':((realized+unrealized)/total_buys*100) if total_buys else 0,
            'Toplam Alış TL':total_buys,'Toplam Satış TL':total_sells,
        })
    return pd.DataFrame(out)


def category_summary():
    df=build_portfolio()
    if df.empty: return df
    return df.groupby('Kategori',as_index=False).agg({
        'Güncel Değer TL':'sum','Kalan Maliyet TL':'sum','Gerçekleşmiş K/Z TL':'sum','Gerçekleşmemiş K/Z TL':'sum','Toplam K/Z TL':'sum'
    })


def date_range_analysis(start, end):
    tx=transactions_df()
    if tx.empty: return pd.DataFrame(), {}
    mask=(pd.to_datetime(tx['tx_date'])>=pd.to_datetime(start)) & (pd.to_datetime(tx['tx_date'])<=pd.to_datetime(end))
    r=tx[mask].copy()
    if r.empty: return r, {'net_cash':0,'buy_total':0,'sell_total':0,'dividend':0,'commission':0}
    r['Tutar TL']=r['quantity'].astype(float)*r['price_try'].astype(float)
    buy=float(r[r['action'].isin(BUY_ACTIONS)]['Tutar TL'].sum())
    sell=float(r[r['action'].isin(SELL_ACTIONS)]['Tutar TL'].sum())
    div=float(r[r['action']=='Temettü']['Tutar TL'].sum())
    comm=float(r['commission_try'].fillna(0).sum())
    return r, {'net_cash':sell+div-buy-comm,'buy_total':buy,'sell_total':sell,'dividend':div,'commission':comm}
