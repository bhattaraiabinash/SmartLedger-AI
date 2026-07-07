# SmartLedger AI

Agentic invoice reconciliation and inventory backend for small local businesses.
Built with Django, DRF, PostgreSQL, Celery, Redis, Docker, and a locally-run
LLM (Ollama) for invoice data extraction.

## Architecture
Invoice upload (image/PDF)

Extraction agent:  Tesseract OCR + Ollama LLM structuring, validated against
a strict pydantic schema before anything touches the database

Reconciliation agent (Phase 3, in progress) - matches line items to inventory
and vendor price rules

Guardrail check (Phase 3) - deterministic rules decide auto-resolve vs.
owner approval

Action agent (Phase 4) - executes stock updates, vendor alerts, reorders;
logs every decision to an audit trail

## Status

- [x] Phase 1: Docker setup, core models, authenticated upload endpoint
- [x] Phase 2: Async OCR + LLM extraction via Celery, with schema-validated
      line items saved to the database
- [ ] Phase 3: Reconciliation engine + guardrail logic
- [ ] Phase 4: Action agent + observability

## How extraction works (Phase 2)

1. Invoice uploaded via API -> saved with `status=pending`, a Celery task
   fires asynchronously.
2. **OCR**: Tesseract extracts raw text (PDFs are converted to page images
   first via `pdf2image`/`poppler-utils`).
3. **LLM structuring**: the raw text is sent to a locally-running Ollama
   model (`llama3`) with a constrained JSON schema, so the model's output
   is shaped correctly rather than free-form text.
4. **Validation**: the LLM's JSON is validated against a stricter pydantic
   schema (decimal parsing, required fields, quantity > 0, etc.) before any
   of it is saved. If validation fails, the invoice is marked `failed` with
   the reason preserved — nothing bad ever reaches the database silently.
5. On success, the invoice's `total_amount`/`invoice_number` are saved and
   each line item becomes an `InvoiceLineItem` row. Re-running extraction
   on the same invoice clears old line items first, so it's idempotent.

## Known limitations

- LLM field extraction isn't perfectly deterministic — occasionally a field
  like `invoice_number` comes back empty even when it's visible in the OCR
  text. This is an inherent characteristic of LLM-based extraction, not a
  bug in the validation layer.
- Only images and PDFs are supported as invoice input.
- Extracted line items aren't yet matched against a product catalog, 
  that's Phase 3 (reconciliation agent).

## Setup

1. Copy `.env.example` to `.env` and fill in real values
2. Make sure Ollama is running locally with a model pulled (e.g. `ollama pull llama3`)
   and reachable from Docker — see note below if you're on Linux
3. `docker compose build`
4. `docker compose up`
5. `docker compose run web python manage.py migrate`
6. `docker compose run web python manage.py createsuperuser`

**Linux note:** Ollama binds to `127.0.0.1` by default, which Docker
containers can't reach. Run:
```bash
sudo systemctl edit ollama
```
and add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
then `sudo systemctl daemon-reload && sudo systemctl restart ollama`.

## API

- `POST /api/invoices/upload/` - upload an invoice (authenticated); triggers
  async extraction
- `GET /api/invoices/` - list your uploaded invoices