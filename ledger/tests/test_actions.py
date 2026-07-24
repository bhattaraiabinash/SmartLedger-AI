import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from ledger.models import Product, Vendor, Invoice, InvoiceLineItem, ReconciliationResult, ActionLog
from ledger.actions import execute_actions_for_invoice, approve_and_execute, reject_action


@pytest.mark.django_db
class TestActionAgent:
    def _make_invoice_with_result(self, decision, quantity=2, matched_product=None):
        user = User.objects.create_user(username="tester", password="pass")
        vendor = Vendor.objects.create(name="Test Vendor")
        invoice = Invoice.objects.create(uploaded_by=user, file="test.pdf", vendor=vendor)
        line_item = InvoiceLineItem.objects.create(
            invoice=invoice,
            raw_item_name="Web Design",
            quantity=quantity,
            unit_price=Decimal("85.00"),
            line_total=Decimal("170.00"),
        )
        result = ReconciliationResult.objects.create(
            line_item=line_item,
            matched_product=matched_product,
            match_score=1.0,
            expected_price=Decimal("85.00"),
            actual_price=Decimal("85.00"),
            price_diff_ratio=0.0,
            decision=decision,
            reason="test",
        )
        return invoice, result

    def test_auto_resolved_restocks_product(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"), stock_quantity=5)
        invoice, result = self._make_invoice_with_result("auto_resolved", quantity=3, matched_product=product)

        logs = execute_actions_for_invoice(invoice)

        product.refresh_from_db()
        assert product.stock_quantity == 8
        assert any(log.action_type == "restock" for log in logs)

    def test_needs_approval_does_not_restock(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"), stock_quantity=5)
        invoice, result = self._make_invoice_with_result("needs_approval", quantity=3, matched_product=product)

        execute_actions_for_invoice(invoice)

        product.refresh_from_db()
        assert product.stock_quantity == 5  # unchanged

    def test_owner_approval_executes_restock(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"), stock_quantity=5)
        invoice, result = self._make_invoice_with_result("needs_approval", quantity=3, matched_product=product)

        log = approve_and_execute(result, approved_by=None)

        product.refresh_from_db()
        assert product.stock_quantity == 8
        assert log.actor == "owner"
        assert log.action_type == "approved"

    def test_owner_rejection_does_not_restock(self):
        product = Product.objects.create(name="Web Design", sku="WD-001", unit_price=Decimal("85.00"), stock_quantity=5)
        invoice, result = self._make_invoice_with_result("needs_approval", quantity=3, matched_product=product)

        log = reject_action(result)

        product.refresh_from_db()
        assert product.stock_quantity == 5
        assert log.action_type == "rejected"