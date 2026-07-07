from celery import shared_task
from django.utils import timezone
from .models import Invoice, InvoiceLineItem
from .ocr_llm import extract_and_validate


@shared_task
def extract_invoice_data(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return f"Invoice {invoice_id} not found"

    validated_data, ocr_text, error = extract_and_validate(invoice.file.path)

    invoice.raw_extracted_text = ocr_text
    invoice.updated_at = timezone.now()

    if error:
        invoice.status = "failed"
        invoice.save()
        return f"Invoice {invoice_id} extraction failed: {error}"

    invoice.status = "extracted"
    invoice.invoice_number = validated_data.invoice_number
    invoice.total_amount = validated_data.total_amount
    invoice.save()

    invoice.line_items.all().delete()

    line_items_to_create = [
        InvoiceLineItem(
            invoice=invoice,
            raw_item_name=item.item_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        for item in validated_data.line_items
    ]
    InvoiceLineItem.objects.bulk_create(line_items_to_create)

    return f"Invoice {invoice_id} extracted successfully: {len(validated_data.line_items)} line items found"