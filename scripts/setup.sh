#!/bin/bash
echo "🚀 Wellco Adult İçerik Üretici - Kurulum"
echo "==========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Python backend setup
echo ""
echo "📦 Python backend kurulumu..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo ""

# Install Playwright browsers
echo "🌐 Playwright tarayıcı kurulumu..."
playwright install chromium
echo ""

cd "$PROJECT_DIR"

# Frontend setup
echo "📦 Next.js frontend kurulumu..."
cd frontend
npm install
echo ""

cd "$PROJECT_DIR"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 .env dosyası oluşturuluyor..."
    cp .env.example .env
    echo "⚠️  .env dosyasını düzenlemeyi unutmayın!"
else
    echo "✅ .env dosyası zaten mevcut"
fi

echo ""
echo "==========================================="
echo "✅ Kurulum tamamlandı!"
echo ""
echo "Sonraki adımlar:"
echo "  1. .env dosyasını düzenleyin (API anahtarları, email ayarları)"
echo "  2. Backend: cd backend && source venv/bin/activate && uvicorn api.server:app --reload --port 8000"
echo "  3. Frontend: cd frontend && npm run dev"
echo "  4. Manuel test: cd backend && python main.py --no-email"
echo "  5. Dashboard: http://localhost:3000"
echo ""
