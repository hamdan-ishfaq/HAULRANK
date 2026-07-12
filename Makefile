.PHONY: api frontend test up

api:
	cd backend && . .venv/bin/activate && python manage.py runserver 127.0.0.1:8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && pytest

up:
	docker compose up --build
