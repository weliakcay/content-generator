# Wellco Adult - Sosyal Medya İçerik Üretici

Pinterest, Instagram ve TikTok'ta wellness/adult kategorisinde trend takibi yapan, AI ile içerik önerileri üreten ve günlük email raporu gönderen sistem.

## Hızlı Başlangıç

```bash
# 1. Kurulum
bash scripts/setup.sh

# 2. .env dosyasını düzenle
cp .env.example .env
# ANTHROPIC_API_KEY ve email ayarlarını gir

# 3. Backend başlat (Terminal 1)
cd backend && source venv/bin/activate && uvicorn api.server:app --reload --port 8000

# 4. Frontend başlat (Terminal 2)
cd frontend && npm run dev

# 5. Dashboard'u aç
open http://localhost:3000
```

## Manuel Pipeline Çalıştırma

```bash
cd backend && source venv/bin/activate

# Tam pipeline (scrape + AI + email)
python main.py

# Sadece AI (scraping olmadan)
python main.py --no-scrape

# Email göndermeden
python main.py --no-email

# Zamanlayıcı (her gün 08:00)
python scheduler.py
```

## Yapı

```
data/              → JSON veri dosyaları (manuel düzenlenebilir)
backend/           → Python (scraping, AI, email, API)
frontend/          → Next.js dashboard
scripts/           → Kurulum ve test scriptleri
```

## Özellikler

- **Trend Takip**: Pinterest, Instagram, TikTok scraping
- **AI İçerik Üretimi**: Claude API ile günlük 5 öneri
- **Email Raporu**: Her sabah detaylı HTML rapor
- **Dashboard**: Öneriler, marka profili, trend takip, istatistikler
- **Öğrenme Sistemi**: Beğen/Beğenme ile sistem tercihlerini öğrenir
- **Arama Şeffaflığı**: Tüm aramalar loglanır
