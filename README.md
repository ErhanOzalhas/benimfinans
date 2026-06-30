# Benim Finans V4.0 — Portföy Motoru

Bu sürümde portföy CSV yerine SQLite tabanlı işlem motoruyla çalışır.

## Yenilikler
- Geçmiş tarihli alış/satış girişi
- Yeni varlık eklerken alış tarihi, alış fiyatı, komisyon ve not
- İşlem geçmişinden portföy üretimi
- Ortalama maliyet
- Gerçekleşmiş ve gerçekleşmemiş kar/zarar
- Varlık ve kategori bazında kar/zarar
- Tarih aralığına göre işlem ve kar/zarar analizi
- Mevcut CSV portföyden otomatik ilk aktarım

## Çalıştırma
```bash
cd ~/Downloads/yatirim_paneli_v2_3
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```
