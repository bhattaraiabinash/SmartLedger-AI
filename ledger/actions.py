from decimal import Decimal
from .models import ReconciliationResult, ActionLog, Product 


def execute_actions_for_invoice(invoice) -> list[ActionLog]:
    
    logs = []
    
    results = ReconciliationResult.objects.filter(line_item__invoice=invoice)
    
    for result in results:
        if result.decision == "auto_resolved":
            logs.append(_restock_product(result))
        else:
            logs.append(_log_pending_approval(result))
            
    for result in results.filter(decision="auto_resolved", matched_product__isnull=False):
        reorder_log = _check_reorder_needed(result.matched_product)
        if reorder_log:
            logs.append(reorder_log)
            
    return logs

def _restock_product(result: ReconciliationResult) -> ActionLog:
    product = result.matched_product
    quantity = result.line_item.quantity
    
    product.stock_quantity += quantity
    product.save()
    
    return ActionLog.objects.create(
        reconciliation_result = result,
        product = product,
        actor="action_agent",
        action_type="restock",
        details=(
            f"Restocked '{product.name}' by {quantity} units "
            f"(new stock: {product.stock_quantity}), based on auto_resolved invoice line item."
             
            
        ),
    )     
    
def _log_pending_approval(result: ReconciliationResult) -> ActionLog:
    item_desc = result.matched_product.name if result.matched_product else result.line_item.raw_item_name
    
    return ActionLog.objects.create(
        reconciliation_result=result,
        product=result.matched_product,
        actor="action_agent",
        action_type = "vendor_alert_drafted" if result.decision == "needs_approval" else "reorder_suggested",
        details=(
            f"No automatic action taken for '{item_desc}' - reconciliation flagged "
            f"'{result.decision}'. Awaiting owner approval via the API before any "
            f"stock or vendor action is executed."
        ),
    )
          
def _check_reorder_needed(product: Product) -> ActionLog | None:
    
    if product.stock_quantity < product.reorder_threshold:
        return ActionLog.objects.ceate(
            reconciliation_result = None,
            product=product,
            actor="action_agent",
            action_type="reorder_sugggested",
            details=(
                f"'{product.name}' stock ({product.stock_quantity}) is still below "
                f"reorder threshold ({product.reorder_threshold}) after restocking. "
                f"Consider placing a new order with {product.preferred_vendor or 'a vendor'}."
            ),
        )
    return None

def approve_and_execute(result: ReconciliationResult, approved_by) -> ActionLog:
   
    from .models import VendorProductPrice
    from .cache import set_cached_vendor_price

    if result.matched_product is None:
        return ActionLog.objects.create(
            reconciliation_result=result,
            product=None,
            actor="owner",
            action_type="approved",
            details=(
                f"Owner approved line item '{result.line_item.raw_item_name}', but no "
                f"product was matched, so no stock action could be taken. Consider "
                f"creating a matching Product record."
            ),
        )

    product = result.matched_product
    quantity = result.line_item.quantity

    product.stock_quantity += quantity
    product.save()

    vendor = result.line_item.invoice.vendor
    if vendor is not None:
        VendorProductPrice.objects.update_or_create(
            vendor=vendor, product=product, defaults={"last_price": result.actual_price}
        )
        set_cached_vendor_price(str(vendor.id), str(product.id), str(result.actual_price))

    return ActionLog.objects.create(
        reconciliation_result=result,
        product=product,
        actor="owner",
        action_type="approved",
        details=(
            f"Owner approved: restocked '{product.name}' by {quantity} units "
            f"(new stock: {product.stock_quantity}). Vendor price history updated "
            f"to {result.actual_price}, since this price is now owner-confirmed."
        ),
    )


def reject_action(result: ReconciliationResult) -> ActionLog:
    return ActionLog.objects.create(
        reconciliation_result=result,
        product=result.matched_product,
        actor="owner",
        action_type="rejected",
        details=(
            f"Owner rejected the reconciliation result for "
            f"'{result.line_item.raw_item_name}'. No stock or price changes made."
        ),
    )