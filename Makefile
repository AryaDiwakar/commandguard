.PHONY: help install test test-phase1 run-backend run-web smoke clean

help:
	@echo "commandguard targets:"
	@echo "  make install     create venv + install backend deps + npm install"
	@echo "  make test        run full backend test gate (pytest)"
	@echo "  make test-phase1 phase 1 gate (same as test today)"
	@echo "  make run-backend  start FastAPI on :8000"
	@echo "  make run-web      start Vite dev on :5173"
	@echo "  make smoke        headless end-to-end check via TestClient"

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r backend/requirements.txt
	cd web && npm install

test:
	cd backend && ../.venv/bin/python -m pytest

test-phase1: test

run-backend:
	cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

run-web:
	cd web && npm run dev

smoke:
	cd backend && ../.venv/bin/python -m scripts.smoke

clean:
	rm -rf backend/.pytest_cache backend/data/*.db .venv web/node_modules web/dist