# Kişisel Yatırım Paneli V2.3

Eklenenler:
- Yeni varlık ekleme: Euro, sterlin, farklı BIST ve ABD hisseleri, diğer varlıklar
- Mevcut portföy miktarlarını düzenleme ve kaydetme
- Altın / Döviz / BIST Hisse / ABD Hisse kategori özeti
- Kategori bazlı portföy dağılımı
- İşlem eklerken listede olmayan varlık yazabilme
- Alış/satış işlemini portföy miktarına otomatik yansıtma
- Manuel fiyat tablosu

## Çalıştırma

```bash
cd ~/Downloads/yatirim_paneli_v2_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Sembol örnekleri

- Euro: type=`fx`, symbol=`EURTRY`
- Sterlin: type=`fx`, symbol=`GBPTRY`
- BIST: type=`bist_stock`, symbol=`TUPRS`
- ABD hissesi: type=`us_stock`, symbol=`NVDA.US`
- Manuel takip: type=`other`, symbol=`BENIM_VARLIK`
