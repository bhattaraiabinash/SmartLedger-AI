from celery import shared_task
from django.utils import timezone
from .models import Invoice, InvoiceLineItem, Vendor
from .ocr_llm import extract_and_validate
from .reconciliation import reconcile_line_item
from .actions import execute_actions_for_invoice


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
    vendor, _ = Vendor.objects.get_or_create(name=validated_data.vendor_name.strip())
    invoice.vendor = vendor
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
        if item.item_name.strip()
    ]
    InvoiceLineItem.objects.bulk_create(line_items_to_create)
    reconcile_invoice.delay(str(invoice.id))

    return f"Invoice {invoice_id} extracted successfully: {len(validated_data.line_items)} line items found"


@shared_task
def reconcile_invoice(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return f"Invoice {invoice_id} not found"
    
    from .models import ReconciliationResult
    ReconciliationResult.objects.filter(line_item__invoice=invoice).delete()
    
    results = [
        reconcile_line_item(line_item, invoice.vendor)
        for line_item in invoice.line_items.all()
        
    ]   
    
    if not results:
        invoice.status = "reconciled"
        invoice.save()
        return f"Invoice {invoice_id} had no line items to reconcile"
    
    decisions = [r.decision for r in results]
    
    if any(d in ("needs_approval", "unmatched") for d in decisions):
        invoice.status = "needs_approval"
    else:
        invoice.status = "reconciled"
        
    invoice.updated_at = timezone.now()
    invoice.save()
    
    auto_count = decisions.count("auto_resolved")
    approval_count = decisions.count("needs_approval")
    unmatched_count = decisions.count("unmatched")
    
    run_actions_for_invoice.delay(str(invoice.id))
    
    return (
        f"Invoice {invoice_id} reconciled: {auto_count} auto-resolved, "
        f"{approval_count} need approval, {unmatched_count} unmatched"
    )   
    
@shared_task
def run_actions_for_invoice(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return f"Invoice {invoice_id} not found"
    
    from .models import ActionLog
    ActionLog.objects.filter(reconciliation_result__line_item__invoice=invoice).delete()
    
    logs = execute_actions_for_invoice(invoice)
    
    restocked = sum(1 for log in logs if log.action_type == "restock")
    pending = len(logs) - restocked
    
    return f"Invoice {invoice_id}: {restocked} products restocked, {pending} actions pending owner approval"            
        