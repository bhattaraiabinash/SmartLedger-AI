import json
import requests
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from decouple import config
from pydantic import ValidationError
from .schemas import ExtractedInvoiceData

OLLAMA_BASE_URL = config("OLLAMA_BASE_URL")
OLLAMA_MODEL = config("OLLAMA_MODEL")

INVOICE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": "string"},
        "invoice_number": {"type": "string"},
        "invoice_date": {"type": "string"},
        "total_amount": {"type": "number"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "number"},
                    "line_total": {"type": "number"},
                },
                "required": ["item_name", "quantity", "unit_price", "line_total"],
            },
        },
    },
    "required": ["vendor_name", "total_amount", "line_items"],
}

EXTRACTION_PROMPT = """You are an invoice data extraction assistant. Given raw OCR text from an invoice, extract the following fields and return ONLY valid JSON, no other text, no markdown code fences:

{{
  "vendor_name": "string",
  "invoice_number": "string or empty",
  "invoice_date": "string or empty (YYYY-MM-DD if determinable, else as written)",
  "total_amount": number,
  "line_items": [
    {{"item_name": "string", "quantity": number, "unit_price": number, "line_total": number}}
  ]
}}

Raw OCR text:
---
{ocr_text}
---

Return ONLY the JSON object, nothing else."""


def run_ocr(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        pages = convert_from_path(file_path, dpi=200)
        text_parts = [pytesseract.image_to_string(page) for page in pages]
        return "\n".join(text_parts)
    else:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)


def structure_with_llm(ocr_text: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text)

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": INVOICE_JSON_SCHEMA,
        },
        timeout=300,
    )
    response.raise_for_status()
    raw_output = response.json()["response"]
    return json.loads(raw_output)


def extract_and_validate(file_path: str) -> tuple[ExtractedInvoiceData | None, str, str | None]:
    ocr_text = run_ocr(file_path)

    if not ocr_text.strip():
        return None, ocr_text, "OCR produced no text — check file quality"

    try:
        raw_json = structure_with_llm(ocr_text)
    except (requests.RequestException, json.JSONDecodeError) as e:
        return None, ocr_text, f"LLM structuring failed: {e}"

    # Normalize empty strings to None for optional fields before pydantic validation
    if raw_json.get("invoice_number") == "":
        raw_json["invoice_number"] = None
    if raw_json.get("invoice_date") == "":
        raw_json["invoice_date"] = None

    try:
        validated = ExtractedInvoiceData(**raw_json)
    except ValidationError as e:
        return None, ocr_text, f"Schema validation failed: {e}"

    return validated, ocr_text, None