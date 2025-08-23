from rest_framework import viewsets
from core.models import FinancialStatementPreparation
from .serializers import FinancialStatementPreparationSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

class FinancialStatementPreparationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing FinancialStatementPreparation records
    """
    queryset = FinancialStatementPreparation.objects.select_related("assigned_to", "client").all()
    serializer_class = FinancialStatementPreparationSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Filtering options
    filterset_fields = {
        "client": ["exact"],
        "status": ["exact", "in"],
        "priority": ["exact", "in"],
        "assigned_to": ["exact"],
        "deadline": ["gte", "lte", "exact"],
    }

    # Search fields
    search_fields = ["type", "needed_data", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering