# SmartLedger AI

Agentic invoice reconciliation and inventory backend for small local businesses.
Built with Django, DRF, PostgreSQL, Celery, Redis, Docker, and a locally-run
LLM (Ollama) for invoice data extraction and deterministic business-rule
reconciliation. 

## Architecture
Invoice upload (image/PDF)
↓
Extraction agent : Tesseract OCR + Ollama LLM structuring, validated against
a strict pydantic schema before anything touches the database
↓
Reconciliation agent : fuzzy-matches line items to the product catalog and
compares prices against vendor-specific price history (Redis-cached)
↓
Guardrail check : deterministic rules (NOT an LLM call) decide auto-resolve
vs. owner approval, with a full audit trail of every decision
↓
Action agent (Phase 4, planned) : executes stock updates, vendor alerts,
reorders based on reconciliation outcomes

## Status

- [x] Phase 1: Docker setup, core models, authenticated upload endpoint
- [x] Phase 2: Async OCR + LLM extraction via Celery, schema-validated
      line items saved to the database
- [x] Phase 3: Reconciliation engine + deterministic guardrail logic
- [ ] Phase 4: Action agent + observability

## How reconciliation works (Phase 3)

1. After extraction succeeds, a separate `reconcile_invoice` Celery task
   fires automatically for the invoice.
2. **Matching**: each line item's raw text (e.g. `"WEB DESIGN SERVICES
   (hourly)"`) is fuzzy-matched against the `Product` catalog using a
   combination of character-sequence similarity and word-overlap scoring,
   this handles OCR text adding extra words around a real product name.
3. **Price comparison**: the matched product's expected price is looked up
   with a three-tier fallback; Redis cache -> vendor-specific price history
   (`VendorProductPrice`) -> the product's generic default price.
4. **Guardrail decision** (plain Python, deterministic, no LLM involved):
   - No product matched -> `needs_approval`
   - Matched, price within 5% of expected -> `auto_resolved`
   - Matched, price differs by more than 5% -> `needs_approval`
5. Every decision is recorded in `ReconciliationResult` with the match
   score, expected vs. actual price, and a human-readable reason; a full
   audit trail, not a black box.
6. Only `auto_resolved` prices are trusted enough to update the vendor's
   price history baseline; a suspicious price never silently becomes
   "normal" just by appearing once.
7. The invoice's overall status rolls up from its line items: any single
   `needs_approval`/unmatched item flags the *whole* invoice for review.

## Known limitations

- LLM field extraction isn't perfectly deterministic, occasionally a field
  like `invoice_number` comes back empty even when visible in the OCR text.
- Fuzzy matching threshold (0.6) is a tunable constant; very short or
  generic product names may need threshold adjustment.
- `VendorProductPrice` tracks only the *latest* price per vendor-product
  pair, not a full price-change history over time.
- A single local CPU-based Ollama instance processes one generation at a
  time,  multiple invoices uploaded in quick succession queue up rather
  than running in parallel (handled gracefully with a 300s timeout).
- Only images and PDFs are supported as invoice input.

## Setup

1. Copy `.env.example` to `.env` and fill in real values
2. Make sure Ollama is running locally with a model pulled (e.g. `ollama pull llama3`)
   and reachable from Docker  (see note below if you're on Linux)
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

- `POST /api/invoices/upload/` : upload an invoice (authenticated); triggers
  async extraction, followed automatically by reconciliation
- `GET /api/invoices/` : list your uploaded invoices

## Example: guardrail in action

Same invoice, two different outcomes depending on price history:

| Scenario | Match score | Expected price | Actual price | Decision |
|---|---|---|---|---|
| Normal reorder | 1.0 | $85.00 | $85.00 | `auto_resolved` |
| Vendor price changed | 1.0 | $50.00 | $85.00 | `needs_approval` (70% over threshold) |