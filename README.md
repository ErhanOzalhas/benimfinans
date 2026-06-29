# Benim Finans V3.1

Mobil uyumlu kişisel yatırım takip paneli.

## Özellikler

- Dashboard kartları
- Kategori bazlı özetler
- Portföy düzenleme
- Yeni varlık ekleme
- İşlem geçmişi
- Portföy geçmiş grafiği
- Alarm listesi
- Excel ve PDF raporu
- Çoklu/veri-yedekli fiyat servisi + manuel fiyat desteği

## Yerel çalıştırma

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

- Repository: `ErhanOzalhas/benimfinans`
- Branch: `main`
- Main file path: `app.py`

> Not: Streamlit Cloud dosya sistemi kalıcı veritabanı için sınırlıdır. Kritik verileri düzenli Excel olarak dışa aktar.
