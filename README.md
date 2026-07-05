# SmartLedger AI

Agentic invoice reconciliation and inventory backend for small local businesses.
Built with Django, DRF, PostgreSQL, Celery, Redis, and Docker.

## Architecture

Invoice upload → Extraction agent (OCR + LLM) → Reconciliation agent →
Guardrail check (auto-resolve vs owner approval) → Action agent (executes
& logs every decision to an audit trail).

## Status

- [x] Phase 1: Docker setup, core models, authenticated upload endpoint
- [ ] Phase 2: Async OCR/LLM extraction via Celery
- [ ] Phase 3: Reconciliation engine + guardrail logic
- [ ] Phase 4: Action agent + observability

## Setup

1. Copy `.env.example` to `.env` and fill in real values
2. `docker compose build`
3. `docker compose up`
4. `docker compose run web python manage.py migrate`
5. `docker compose run web python manage.py createsuperuser`

## API (so far)

- `POST /api/invoices/upload/` — upload an invoice (authenticated)
- `GET /api/invoices/` — list your uploaded invoices