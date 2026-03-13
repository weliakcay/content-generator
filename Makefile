.PHONY: setup backend frontend dev pipeline test test-email

setup:
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt && playwright install chromium
	cd frontend && npm install
	cp -n .env.example .env || true
	@echo "Setup tamamlandı! .env dosyasını düzenleyin."

backend:
	cd backend && . venv/bin/activate && uvicorn api.server:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "İki terminal açın:"
	@echo "  Terminal 1: make backend"
	@echo "  Terminal 2: make frontend"

pipeline:
	cd backend && . venv/bin/activate && python main.py

scheduler:
	cd backend && . venv/bin/activate && python scheduler.py

test-email:
	cd backend && . venv/bin/activate && python ../scripts/test_email.py
