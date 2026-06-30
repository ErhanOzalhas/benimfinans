# Benim Finans V6.0 — Supabase Cloud DB

Bu sürümde veriler artık Streamlit sunucusundaki geçici dosyada değil, **Supabase PostgreSQL** üzerinde tutulabilir.
Böylece iPhone, Mac veya başka cihazdan yaptığın ekleme/düzenleme/silme işlemleri kalıcı olur.

## Eklenenler
- Supabase Cloud Database desteği
- SQLite yerel yedek/fallback
- Mobilde girilen işlemlerin kalıcı saklanması
- V5.0 portföy motoru korunur: geçmiş tarihli alış/satış, ortalama maliyet, K/Z, ürün silme/arşivleme

## 1. Supabase kurulumu

1. https://supabase.com üzerinde yeni proje oluştur.
2. Project Settings > API bölümünden şunları al:
   - Project URL
   - anon public key
3. Supabase > SQL Editor > New Query aç.
4. `docs/supabase_schema.sql` dosyasındaki SQL'i yapıştır ve Run de.

## 2. Streamlit Secrets

Streamlit Cloud > uygulaman > Manage app > Settings > Secrets bölümüne şunu ekle:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJ...anon_public_key..."
```

Kaydet, sonra **Reboot app** yap.

## 3. Yerel çalıştırma

Supabase secrets yoksa uygulama yerelde otomatik SQLite kullanır:

```bash
cd ~/Downloads/yatirim_paneli_v2_3
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Yerelde de Supabase kullanmak istersen `.streamlit/secrets.toml` oluştur:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "anon-public-key"
```

## 4. GitHub'a gönderme

```bash
git add .
git commit -m "V6.0 Supabase cloud database"
git push
```
