from datetime import datetime
from django.contrib.auth.models import User
from rest_framework import serializers

from core.models import (
    AccountingAudit,
    AppLog,
    Client,
    Compliance,
    FinanceImplementation,
    FinancialStatementPreparation,
    HumanResourceImplementation,
    MiscellaneousTasks,
    Notification,
    TaxCase,
    User,
)
from core.utils import get_today_local
from core.choices import TaskStatus

# =======================
# Mini Serializers
# =======================


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "role",
            "fullname",
            "is_admin",
        ]


class ClientMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "name"]


# =======================
# Full Serializers
# =======================


class UserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "username",
            "email",
            "fullname",
            "role",
            "is_active",
            "last_login",
            "password",
            "is_admin",
            "has_logs",
        ]

    def validate(self, data):
        if (
            User.objects.filter(
                first_name__iexact=data.get("first_name"),
                middle_name__iexact=data.get("middle_name"),
                last_name__iexact=data.get("last_name"),
            )
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise serializers.ValidationError("This user already exists.")
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data["username"] = validated_data.get("username", "").strip().lower()
        validated_data["first_name"] = (
            validated_data.get("first_name", "").strip().title()
        )
        validated_data["middle_name"] = (
            validated_data.get("middle_name", "").strip().title()
        )
        validated_data["last_name"] = (
            validated_data.get("last_name", "").strip().title()
        )
        validated_data["email"] = validated_data.get("email", "").strip().lower()

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance.username = (
            validated_data.get("username", instance.username).strip().lower()
        )
        instance.first_name = (
            validated_data.get("first_name", instance.first_name).strip().title()
        )
        instance.middle_name = (
            validated_data.get("middle_name", instance.middle_name).strip().title()
        )
        instance.last_name = (
            validated_data.get("last_name", instance.last_name).strip().title()
        )
        instance.email = validated_data.get("email", instance.email).strip().lower()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class ClientSerializer(serializers.ModelSerializer):
    created_by = UserMiniSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class AccountingAuditSerializer(serializers.ModelSerializer):
    """Serializer for AccountingAudit model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = AccountingAudit
        fields = [
            "id",
            "client",
            "client_detail",
            "description",
            "status",
            "period_covered",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class AccountingAuditListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = AccountingAudit
        fields = [
            "id",
            "client_name",
            "description",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class ComplianceSerializer(serializers.ModelSerializer):
    """Serializer for Compliance model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = Compliance
        fields = [
            "id",
            "client",
            "client_detail",
            "description",
            "steps",
            "requirements",
            "status",
            "period_covered",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class ComplianceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = Compliance
        fields = [
            "id",
            "client_name",
            "description",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class FinancialStatementPreparationSerializer(serializers.ModelSerializer):
    """Serializer for FinancialStatementPreparation model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
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


class FinancialStatementPreparationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = FinancialStatementPreparation
        fields = [
            "id",
            "client_name",
            "type",
            "needed_data",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class FinanceImplementationSerializer(serializers.ModelSerializer):
    """Serializer for FinanceImplementation model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = FinanceImplementation
        fields = [
            "id",
            "client",
            "client_detail",
            "description",
            "status",
            "period_covered",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class FinanceImplementationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = FinanceImplementation
        fields = [
            "id",
            "client_name",
            "description",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class HumanResourceImplementationSerializer(serializers.ModelSerializer):
    """Serializer for HumanResourceImplementation model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = HumanResourceImplementation
        fields = [
            "id",
            "client",
            "client_detail",
            "description",
            "status",
            "period_covered",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class HumanResourceImplementationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = HumanResourceImplementation
        fields = [
            "id",
            "client_name",
            "description",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class MiscellaneousTasksSerializer(serializers.ModelSerializer):
    """Serializer for MiscellaneousTasks model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)

    class Meta:
        model = MiscellaneousTasks
        fields = [
            "id",
            "client",
            "client_detail",
            "area",
            "description",
            "status",
            "period_covered",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class MiscellaneousTasksListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = MiscellaneousTasks
        fields = [
            "id",
            "client_name",
            "area",
            "description",
            "status",
            "assigned_to",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "completion_date",
            "last_update",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class ClientBirthdaySerializer(serializers.ModelSerializer):
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ["name", "date_of_birth", "days_remaining"]
        read_only_fields = ["created_at", "updated_at"]

    def get_days_remaining(self, obj):
        return (obj.date_of_birth - get_today_local()).days


class NotificationSerializer(serializers.ModelSerializer):
    recipient = UserMiniSerializer(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
    timesince_created = serializers.CharField(read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["created_at"]


class TaxCaseSerializer(serializers.ModelSerializer):
    client_detail = ClientMiniSerializer(source="client", read_only=True)
    assigned_to_detail = UserMiniSerializer(source="assigned_to", read_only=True)

    class Meta:
        model = TaxCase
        fields = [
            "id",
            "client",
            "client_id",
            "client_detail",
            "category",
            "type",
            "form",
            "period_covered",
            "working_paper",
            "tax_payable",
            "last_followup",
            "assigned_to",
            "assigned_to_id",
            "assigned_to_detail",
            "status",
            "priority",
            "engagement_date",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date
        if engagement_date and deadline and deadline < engagement_date:
            raise serializers.ValidationError(
                "Deadline cannot be earlier than engagement date."
            )

        # Validate that completion date is not before engagement date
        if engagement_date and completion_date and completion_date < engagement_date:
            raise serializers.ValidationError(
                "Completion date cannot be earlier than engagement date."
            )

        # Validate that date complied is not before engagement date
        if engagement_date and date_complied and date_complied < engagement_date:
            raise serializers.ValidationError(
                "Date complied cannot be earlier than engagement date."
            )

        return data


class TaxCaseListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_tin = serializers.CharField(source="client.tin", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)

    completion_date = serializers.DateTimeField(
        format="%b %d, %Y %I:%M %p", read_only=True
    )

    category_name = serializers.SerializerMethodField()
    type_name = serializers.SerializerMethodField()
    form_name = serializers.SerializerMethodField()
    deadline_days_remaining = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = TaxCase
        fields = [
            "id",
            "client_name",
            "client_tin",
            "category",
            "category_name",
            "type",
            "type_name",
            "form",
            "form_name",
            "period_covered",
            "tax_payable",
            "last_followup",
            "assigned_to_name",
            "priority",
            "engagement_date",
            "deadline",
            "last_update",
            "status",
            "date_complied",
            "completion_date",
            "deadline_days_remaining",
            "remarks",
            "status_history",
        ]

    def get_category_name(self, obj):
        return obj.get_category_display()

    def get_type_name(self, obj):
        return obj.get_type_display()

    def get_form_name(self, obj):
        return obj.get_form_display()

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_status_history(self, obj):
        history = obj.status_history or []
        formatted = []
        for item in history:
            formatted.append(
                {
                    "status": TaskStatus(item["status"]).label,
                    "remarks": item["remarks"],
                    "date": datetime.fromisoformat(item["date"]).strftime(
                        "%B %d, %Y %I:%M %p"
                    ),
                }
            )
        return formatted


class AppLogSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = AppLog
        fields = "__all__"
        read_only_fields = ["created_at"]
