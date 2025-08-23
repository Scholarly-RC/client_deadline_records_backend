from rest_framework import serializers
from core.models import FinancialStatementPreparation
from core.serializers import UserMiniSerializer, ClientMiniSerializer

class FinancialStatementPreparationSerializer(serializers.ModelSerializer):
    """Serializer for FinancialStatementPreparation model"""

    assigned_to_detail = UserMiniSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = FinancialStatementPreparation
        fields = [
            "id",
            "client",
            "client_detail",
            "type",
            "needed_data",
            "status",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]
