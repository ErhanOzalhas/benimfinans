# Benim Finans V6.1 — Cloud Engine

Bu sürümde uygulama Supabase Cloud Database ile çalışır. Streamlit Cloud üzerinde telefon, Mac ve web aynı veriyi görür.

## Eklenenler
- `SUPABASE_ANON_KEY` desteği
- Supabase tablo şeması V6.1 ile güncellendi
- Günlük portföy değeri kaydı (`daily_snapshots`)
- Ana sayfada portföy geçmiş grafiği
- SQLite sadece yerel fallback olarak kalır

## Supabase SQL
Supabase > SQL Editor > New Query içine `docs/supabase_schema.sql` dosyasını yapıştırıp Run de.

## Streamlit Secrets
```toml
SUPABASE_URL = "https://lsiauqlsohdfynwuobqh.supabase.co"
SUPABASE_ANON_KEY = "anon-public-key"
```

## Yayın
```bash
git add .
git commit -m "V6.1 Supabase cloud engine"
git push origin main
```

Sonra Streamlit Cloud > Manage app > Reboot app.
