# SmartLedger AI

Agentic invoice reconciliation and inventory backend for small local businesses.
Built with Django, DRF, PostgreSQL, Celery, Redis, Docker, and a locally-run
LLM (Ollama) for invoice data extraction and deterministic business-rule
reconciliation.

## Architecture

Invoice upload (image/PDF)
↓
Extraction agent — Tesseract OCR + Ollama LLM structuring, validated against
a strict pydantic schema before anything touches the database
↓
Reconciliation agent — fuzzy-matches line items to the product catalog and
compares prices against vendor-specific price history (Redis-cached)
↓
Guardrail check — deterministic rules (NOT an LLM call) decide auto-resolve
vs. owner approval, with a full audit trail of every decision
↓
Action agent — executes stock updates for trusted results, or logs a
pending action awaiting explicit owner approval via the API; every action
is recorded in a full audit trail (ActionLog)


## Status

- [x] Phase 1: Docker setup, core models, authenticated upload endpoint
- [x] Phase 2: Async OCR + LLM extraction via Celery, schema-validated
      line items saved to the database
- [x] Phase 3: Reconciliation engine + deterministic guardrail logic
- [x] Phase 4: Action agent, owner-approval API, drf-spectacular docs,
      pytest test suite

## How the action agent works (Phase 4)

1. After reconciliation, a separate `run_actions_for_invoice` Celery task
   fires automatically for the invoice.
2. **`auto_resolved`** line items → stock is restocked immediately,
   trusted without human involvement.
3. **`needs_approval` / `unmatched`** line items → no automatic action;
   a pending `ActionLog` entry is created instead.
4. The owner reviews pending items via `GET /api/reconciliation/pending/`
   and decides via `POST /api/reconciliation/{id}/decide/` with
   `{"decision": "approve"}` or `{"decision": "reject"}`.
5. Approval executes the restock **and** updates the vendor's trusted
   price history — the same "trust must be earned" principle used for
   auto-resolve, just earned via explicit human sign-off instead.
6. Every action — automatic or owner-approved — is recorded in
   `ActionLog` with a clear `actor` field distinguishing agent decisions
   from human ones.

## API documentation

Full interactive API docs (Swagger UI): `http://localhost:8000/api/docs/`
Alternative read-only docs (ReDoc): `http://localhost:8000/api/redoc/`
Raw OpenAPI schema: `http://localhost:8000/api/schema/`

## Testing

```bash
docker compose run web pytest -v
```

22 automated tests cover the fuzzy matching algorithm, price comparison
and caching logic, the guardrail decision tree, and the action agent's
restock/approval/rejection behavior. OCR/LLM extraction itself is
excluded from automated tests deliberately — it depends on a live local
Ollama instance and isn't deterministic, so it's been verified extensively
through manual end-to-end testing instead (documented below).

## Known limitations

- LLM field extraction isn't perfectly deterministic — occasionally a
  field like `invoice_number` comes back empty, or a quantity is misread,
  even when clearly visible in the OCR text. This is a genuine, observed
  characteristic of LLM-based extraction, not a bug in the validation
  layer — and it's exactly why the guardrail/approval system exists: an
  extraction error on an auto-resolved item still propagates into a real
  stock change, but a human always reviews anything the guardrail doesn't
  fully trust.
- Fuzzy matching threshold (0.6) is a tunable constant; very short or
  generic product names may need threshold adjustment.
- `VendorProductPrice` tracks only the *latest* price per vendor-product
  pair, not a full price-change history over time.
- A single local CPU-based Ollama instance processes one generation at a
  time — multiple invoices uploaded in quick succession queue up rather
  than running in parallel (handled gracefully with a 300s timeout).
- Only images and PDFs are supported as invoice input.

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

- `POST /api/invoices/upload/` — upload an invoice (authenticated);
  triggers async extraction → reconciliation → action, automatically
- `GET /api/invoices/` — list your uploaded invoices
- `GET /api/reconciliation/pending/` — list reconciliation results
  awaiting owner approval
- `POST /api/reconciliation/{id}/decide/` — approve or reject a pending
  reconciliation result

## Example: guardrail in action

Same invoice, two different outcomes depending on price history:

| Scenario | Match score | Expected price | Actual price | Decision |
|---|---|---|---|---|
| Normal reorder | 1.0 | $85.00 | $85.00 | `auto_resolved` |
| Vendor price changed | 1.0 | $50.00 | $85.00 | `needs_approval` (70% over threshold) |