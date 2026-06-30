# Benim Finans V5.0 — MyFin

Profesyonel portföy motoru + mobil/PWA hazırlığı.

## Öne çıkanlar
- SQLite tabanlı işlem motoru
- Geçmiş tarihli alış/satış, temettü, komisyon
- Yeni varlık eklerken alış tarihi ve maliyet bilgisi
- Varlık bazında tek tek silme / arşivleme
- Tüm portföyü temizleme
- Ortalama maliyet, gerçekleşmiş ve gerçekleşmemiş K/Z
- Kategori ve seçilen tarih aralığı analizi
- Mobil uyumlu MyFin tasarım
- PWA hazırlığı: logo, manifest, tema rengi

## Çalıştırma
```bash
cd ~/Downloads/yatirim_paneli_v2_3
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Yayınlama
```bash
git add .
git commit -m "V5.0 MyFin portfoy motoru ve PWA"
git push
```
