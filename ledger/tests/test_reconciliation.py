import pytest
from decimal import Decimal
from ledger.models import Product, Vendor, VendorProductPrice
from ledger.reconciliation import (
    char_similarity,
    token_overlap,
    similarity,
    find_best_product_match,
    get_expected_price,
    price_difference_ratio,
    reconcile_line_item,
)
from ledger.models import Invoice, InvoiceLineItem
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestSimilarityScoring:
    def test_char_similarity_identical_strings(self):
        assert char_similarity("Web Design", "Web Design") == 1.0

    def test_char_similarity_is_case_insensitive(self):
        assert char_similarity("WEB DESIGN", "web design") == 1.0

    def test_token_overlap_handles_extra_words(self):
        # This is the exact real bug we hit: extra words shouldn't tank the score
        score = token_overlap("WEB DESIGN SERVICES (hourly)", "Web Design")
        assert score == 1.0

    def test_similarity_takes_the_best_of_both_methods(self):
        score = similarity("WEB DESIGN SERVICES (hourly)", "Web Design")
        assert score == 1.0

    def test_unrelated_strings_score_low(self):
        score = similarity("Completely Unrelated Thing", "Web Design")
        assert score < 0.3


@pytest.mark.django_db
class TestProductMatching:
    def test_finds_exact_match(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        matched, score = find_best_product_match("Web Design")
        assert matched == product
        assert score == 1.0

    def test_finds_fuzzy_match_with_extra_words(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        matched, score = find_best_product_match("WEB DESIGN SERVICES (hourly)")
        assert matched == product

    def test_returns_none_below_threshold(self):
        Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        matched, score = find_best_product_match("Completely Unrelated Thing")
        assert matched is None

    def test_returns_none_with_empty_catalog(self):
        matched, score = find_best_product_match("Anything")
        assert matched is None
        assert score == 0.0


@pytest.mark.django_db
class TestExpectedPrice:
    def test_falls_back_to_product_default_with_no_vendor(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        price = get_expected_price(None, product)
        assert price == Decimal("85.00")

    def test_uses_vendor_specific_price_when_available(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        vendor = Vendor.objects.create(name="Test Vendor")
        VendorProductPrice.objects.create(vendor=vendor, product=product, last_price=Decimal("90.00"))

        price = get_expected_price(vendor, product)
        assert price == Decimal("90.00")


class TestPriceDifferenceRatio:
    def test_calculates_correct_percentage(self):
        ratio = price_difference_ratio(Decimal("90.00"), Decimal("85.00"))
        assert abs(ratio - Decimal("0.0556")) < Decimal("0.001")

    def test_zero_expected_with_nonzero_actual_is_full_difference(self):
        ratio = price_difference_ratio(Decimal("0"), Decimal("50.00"))
        assert ratio == Decimal("1.0")


@pytest.mark.django_db
class TestReconciliationGuardrail:
    def _make_line_item(self, item_name="Web Design", unit_price=Decimal("85.00")):
        user = User.objects.create_user(username="tester", password="pass")
        invoice = Invoice.objects.create(uploaded_by=user, file="test.pdf")
        return InvoiceLineItem.objects.create(
            invoice=invoice,
            raw_item_name=item_name,
            quantity=1,
            unit_price=unit_price,
            line_total=unit_price,
        )

    def test_matched_product_within_tolerance_auto_resolves(self):
        Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        line_item = self._make_line_item(unit_price=Decimal("85.00"))

        result = reconcile_line_item(line_item, vendor=None)

        assert result.decision == "auto_resolved"
        assert result.matched_product is not None

    def test_matched_product_with_price_gap_needs_approval(self):
        Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("50.00"))
        line_item = self._make_line_item(unit_price=Decimal("85.00"))

        result = reconcile_line_item(line_item, vendor=None)

        assert result.decision == "needs_approval"

    def test_unmatched_item_needs_approval(self):
        line_item = self._make_line_item(item_name="Something Unrelated")

        result = reconcile_line_item(line_item, vendor=None)

        assert result.decision == "unmatched"
        assert result.matched_product is None

    def test_only_auto_resolved_updates_price_history(self):
        Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"))
        vendor = Vendor.objects.create(name="Test Vendor")
        line_item = self._make_line_item(unit_price=Decimal("85.00"))

        reconcile_line_item(line_item, vendor=vendor)

        assert VendorProductPrice.objects.filter(vendor=vendor).exists()

    def test_needs_approval_does_not_update_price_history(self):
        Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("50.00"))
        vendor = Vendor.objects.create(name="Test Vendor")
        line_item = self._make_line_item(unit_price=Decimal("85.00"))

        reconcile_line_item(line_item, vendor=vendor)

        assert not VendorProductPrice.objects.filter(vendor=vendor).exists()