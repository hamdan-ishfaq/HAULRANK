.PHONY: api frontend test up e2e e2e-live down

api:
	cd backend && . .venv/bin/activate && python manage.py runserver 0.0.0.0:8000

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

test:
	cd backend && . .venv/bin/activate && pytest

up:
	docker compose up --build -d

down:
	docker compose down

e2e:
	python3 scripts/e2e.py http://127.0.0.1:8000 http://127.0.0.1:5173

e2e-live:
	python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app
