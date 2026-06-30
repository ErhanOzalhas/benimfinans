# Benim Finans V3.4

Bu sürümde eklenenler:

- Geçmiş tarihli alım/satım girişi
- Alış işlemlerinde ağırlıklı maliyet güncelleme
- Varlık bazında toplam kâr/zarar
- Kategori bazında toplam kâr/zarar
- Seçilen tarih aralığındaki işlemlere göre yaklaşık kâr/zarar analizi
- Kâr/Zarar menüsü
- İşlem geçmişini düzenleme

> Not: Tarih aralığı K/Z hesabı, seçilen aralıkta girilen işlemleri bugünkü fiyatlarla değerlendirir. Tam tarihsel fiyat bazlı getiri hesabı için sonraki sürümde geçmiş fiyat verisi modülü eklenecek.

## Çalıştırma

```bash
cd ~/Downloads/yatirim_paneli_v2_3
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```
