from __future__ import annotations
import requests
import pandas as pd
from datetime import datetime
from database.db import assets_df, save_price, price_cache_df

HEADERS={'User-Agent':'Mozilla/5.0'}


def _get_json(url, timeout=8):
    r=requests.get(url,headers=HEADERS,timeout=timeout)
    r.raise_for_status(); return r.json()


def yahoo_chart(symbol):
    # TRY prices for BIST with .IS; USD assets later converted by USDTRY
    ysym=symbol
    if symbol.endswith('.US'):
        ysym=symbol.replace('.US','')
    elif symbol in ['ASELS','ENJSA','SISE','ISCTR']:
        ysym=symbol+'.IS'
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range=1d&interval=1d'
    data=_get_json(url)
    result=data['chart']['result'][0]
    price=result['meta'].get('regularMarketPrice') or result['indicators']['quote'][0]['close'][-1]
    currency=result['meta'].get('currency','')
    return float(price), currency, f'Yahoo {ysym}'


def stooq_price(symbol):
    # Stooq CSV fallback
    s=symbol.lower()
    if symbol.endswith('.US'): s=symbol.replace('.US','.us').lower()
    elif symbol in ['ASELS','ENJSA','SISE','ISCTR']: s=symbol.lower()+'.tr'
    url=f'https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv'
    df=pd.read_csv(url)
    close=df.iloc[0].get('Close')
    if str(close)=='N/D': raise ValueError('Stooq fiyat yok')
    return float(close), 'USD' if symbol.endswith('.US') else 'TRY', f'Stooq {s}'


def usdtry():
    try:
        data=_get_json('https://open.er-api.com/v6/latest/USD')
        return float(data['rates']['TRY']), 'open.er-api'
    except Exception:
        p,c,s=yahoo_chart('USDTRY=X')
        return p,s


def eurtry():
    data=_get_json('https://open.er-api.com/v6/latest/EUR')
    return float(data['rates']['TRY']), 'open.er-api'


def gbptry():
    data=_get_json('https://open.er-api.com/v6/latest/GBP')
    return float(data['rates']['TRY']), 'open.er-api'


def gram_gold_try():
    # Approx gram altın = XAUUSD / 31.1034768 * USDTRY
    xau,cur,src=yahoo_chart('GC=F')
    u,usrc=usdtry()
    return (xau/31.1034768)*u, f'{src}+{usrc}'


def get_price_try(symbol, category='', manual_price=0):
    symbol=str(symbol).upper()
    try:
        if symbol in ['USDTRY','USD','DOLAR']:
            p,src=usdtry(); return p, src
        if symbol in ['EURTRY','EUR','EURO']:
            p,src=eurtry(); return p, src
        if symbol in ['GBPTRY','GBP','STERLIN']:
            p,src=gbptry(); return p, src
        if symbol in ['GRAM_ALTIN','ALTIN','XAUTRYG']:
            p,src=gram_gold_try(); return p, src
        p,cur,src=yahoo_chart(symbol)
        if cur == 'USD' or symbol.endswith('.US'):
            u,usrc=usdtry(); return p*u, f'{src}+USDTRY'
        return p, src
    except Exception:
        try:
            p,cur,src=stooq_price(symbol)
            if cur == 'USD' or symbol.endswith('.US'):
                u,usrc=usdtry(); return p*u, f'{src}+USDTRY'
            return p, src
        except Exception:
            if manual_price and float(manual_price)>0:
                return float(manual_price), 'Manuel fiyat'
            cache=price_cache_df()
            if cache is None or cache.empty or 'symbol' not in cache.columns:
                return float(manual_price or 0), "Manuel fiyat"
            row=cache[cache['symbol']==symbol]
            if not row.empty:
                return float(row.iloc[0]['price_try']), 'Cache'
            return 0.0, 'Fiyat yok'


def refresh_all_prices():
    rows=[]
    for _,a in assets_df().iterrows():
        p,src=get_price_try(a['symbol'], a['category'], a.get('manual_price_try',0))
        if p>0: save_price(a['symbol'], p, src)
        rows.append({'symbol':a['symbol'],'price_try':p,'source':src})
    return pd.DataFrame(rows)
