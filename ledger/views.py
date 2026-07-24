from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Invoice, ReconciliationResult
from .serializers import InvoiceUploadSerializer, ReconciliationResultSerializer
from .tasks import extract_invoice_data
from .actions import approve_and_execute, reject_action


class InvoiceUploadView(generics.CreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceUploadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        invoice = serializer.save(uploaded_by=self.request.user, status="pending")
        extract_invoice_data.delay(str(invoice.id))
        
class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceUploadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(uploaded_by=self.request.user)
    
class PendingReconciliationResultsView(generics.ListAPIView):
    """Lists everything currently awaiting owner approval."""
    serializer_class = ReconciliationResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReconciliationResult.objects.filter(
            decision__in=["needs_approval", "unmatched"],
            line_item__invoice__uploaded_by=self.request.user,
        ).exclude(action_logs__actor="owner")


class ReconciliationResultDecisionView(APIView):
    """POST {"decision": "approve"} or {"decision": "reject"} to act on a pending result."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            result = ReconciliationResult.objects.get(
                pk=pk, line_item__invoice__uploaded_by=request.user
            )
        except ReconciliationResult.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            return Response(
                {"detail": "decision must be 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if decision == "approve":
            log = approve_and_execute(result, approved_by=request.user)
        else:
            log = reject_action(result)

        return Response(
            {"action_type": log.action_type, "details": log.details},
            status=status.HTTP_200_OK,
        )    