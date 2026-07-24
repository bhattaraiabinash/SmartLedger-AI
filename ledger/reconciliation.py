
from difflib import SequenceMatcher
from decimal import Decimal
from .models import (
    Product, VendorProductPrice, Vendor, 
    InvoiceLineItem, ReconciliationResult
)
from .cache import get_cached_vendor_price, set_cached_vendor_price


MATCH_THRESHOLD = 0.6

def char_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def token_overlap(a: str, b:str) -> float:
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    smaller = min(len(a_words), len(b_words))
    overlap = len(a_words & b_words)
    return overlap / smaller
    
    
def similarity(a: str, b: str) -> float:
    return max(char_similarity(a,b), token_overlap(a,b))

def find_best_product_match(raw_item_name: str) -> tuple[Product | None, float]:
    
    best_product = None
    best_score = 0.0
    
    for product in Product.objects.all():
        score = similarity(raw_item_name, product.name)
        if score > best_score:
            best_score = score
            best_product = product
            
    if best_score >= MATCH_THRESHOLD:
        return best_product, best_score
    return None, best_score    

PRICE_DIFF_AUTO_RESOLVE_THRESHOLD = Decimal("0.05")  


def get_expected_price(vendor: Vendor | None, product: Product) -> Decimal:
   
    if vendor is not None:
        cached = get_cached_vendor_price(str(vendor.id), str(product.id))
        if cached is not None:
            return Decimal(cached)

        vendor_price = VendorProductPrice.objects.filter(vendor=vendor, product=product).first()
        if vendor_price is not None:
            set_cached_vendor_price(str(vendor.id), str(product.id), str(vendor_price.last_price))
            return vendor_price.last_price

    return product.unit_price


def price_difference_ratio(expected: Decimal, actual: Decimal) -> Decimal:
    
    if expected == 0:
        return Decimal("1.0") if actual != 0 else Decimal("0.0")
    return abs(actual - expected) / expected    

def reconcile_line_item(line_item: InvoiceLineItem, vendor) -> ReconciliationResult:
   
    product, match_score = find_best_product_match(line_item.raw_item_name)

    if product is None:
        result = ReconciliationResult.objects.create(
            line_item=line_item,
            matched_product=None,
            match_score=match_score,
            expected_price=None,
            actual_price=line_item.unit_price,
            price_diff_ratio=None,
            decision="unmatched",
            reason=f"No product matched '{line_item.raw_item_name}' (best score: {match_score:.2f}, below threshold {MATCH_THRESHOLD})",
        )
        return result

    expected_price = get_expected_price(vendor, product)
    diff_ratio = price_difference_ratio(expected_price, line_item.unit_price)

    if diff_ratio <= PRICE_DIFF_AUTO_RESOLVE_THRESHOLD:
        decision = "auto_resolved"
        reason = (
            f"Matched '{product.name}' (score {match_score:.2f}); "
            f"price {line_item.unit_price} within {PRICE_DIFF_AUTO_RESOLVE_THRESHOLD:.0%} "
            f"of expected {expected_price}"
        )
    else:
        decision = "needs_approval"
        reason = (
            f"Matched '{product.name}' (score {match_score:.2f}); "
            f"price {line_item.unit_price} differs from expected {expected_price} "
            f"by {diff_ratio:.1%}, exceeding {PRICE_DIFF_AUTO_RESOLVE_THRESHOLD:.0%} threshold"
        )

    result = ReconciliationResult.objects.create(
        line_item=line_item,
        matched_product=product,
        match_score=match_score,
        expected_price=expected_price,
        actual_price=line_item.unit_price,
        price_diff_ratio=float(diff_ratio),
        decision=decision,
        reason=reason,
    )

    
    if decision == "auto_resolved" and vendor is not None:
        VendorProductPrice.objects.update_or_create(
            vendor=vendor, product=product, defaults={"last_price": line_item.unit_price}
        )
        set_cached_vendor_price(str(vendor.id), str(product.id), str(line_item.unit_price))

    return result