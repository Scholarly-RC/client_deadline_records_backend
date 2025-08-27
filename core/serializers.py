from datetime import datetime

from django.contrib.auth.models import User
from rest_framework import serializers

from core.choices import TaskStatus
from core.models import (
    AppLog,
    Client,
    Notification,
    Task,
    TaskApproval,
    TaskStatusHistory,
    User,
)
from core.utils import get_today_local

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


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model"""

    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    client_detail = ClientMiniSerializer(source="client", read_only=True)
    category_specific_fields = serializers.ReadOnlyField()

    # Approval-related read-only fields
    pending_approver = UserMiniSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "client",
            "client_detail",
            "category",
            "description",
            "status",
            "assigned_to",
            "assigned_to_detail",
            "priority",
            "deadline",
            "remarks",
            "date_complied",
            "completion_date",
            "last_update",
            "period_covered",
            "engagement_date",
            # Category-specific fields
            "steps",
            "requirements",
            "type",
            "needed_data",
            "area",
            "tax_category",
            "tax_type",
            "form",
            "working_paper",
            "tax_payable",
            "last_followup",
            "category_specific_fields",
            # Approval-related fields
            "current_approval_step",
            "requires_approval",
            "pending_approver",
        ]
        read_only_fields = ["id", "last_update"]

    def validate(self, data):
        """Custom validation for date fields"""
        engagement_date = data.get("engagement_date")
        deadline = data.get("deadline")
        completion_date = data.get("completion_date")
        date_complied = data.get("date_complied")

        # Validate that deadline is after engagement date if both are provided
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


class TaskListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Task list views"""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True
    )
    engagement_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    deadline = serializers.DateField(format="%b %d, %Y", read_only=True)
    completion_date = serializers.DateField(format="%b %d, %Y", read_only=True)
    last_update = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    deadline_days_remaining = serializers.SerializerMethodField()
    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    category_specific_fields = serializers.ReadOnlyField()

    # Approver details
    pending_approver = UserMiniSerializer(read_only=True)
    current_approval_step = serializers.IntegerField(read_only=True)
    requires_approval = serializers.BooleanField(read_only=True)
    all_approvers = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "client_name",
            "category",
            "category_display",
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
            "category_specific_fields",
            # Approval-related fields
            "pending_approver",
            "current_approval_step",
            "requires_approval",
            "all_approvers",
        ]

    def get_deadline_days_remaining(self, obj):
        if obj.deadline:
            return (obj.deadline - get_today_local()).days
        return None

    def get_all_approvers(self, obj):
        """Get all approvers in the approval workflow (both pending and completed)"""
        if not obj.requires_approval:
            return []

        approvers = []
        for approval in obj.approvals.all().order_by("step_number"):
            approver_data = {
                "step": approval.step_number,
                "approver": UserMiniSerializer(approval.approver).data,
                "action": approval.action,
                "action_display": approval.get_action_display(),
                "comments": approval.comments,
                "is_current": (
                    approval.step_number == obj.current_approval_step
                    and approval.action == "pending"
                ),
                "created_at": (
                    approval.created_at.strftime("%b %d, %Y at %I:%M %p")
                    if approval.created_at
                    else None
                ),
                "updated_at": (
                    approval.updated_at.strftime("%b %d, %Y at %I:%M %p")
                    if approval.updated_at
                    else None
                ),
            }
            approvers.append(approver_data)

        return approvers


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


class AppLogSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = AppLog
        fields = "__all__"
        read_only_fields = ["created_at"]


class TaskStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for TaskStatusHistory model"""

    changed_by = UserMiniSerializer(read_only=True)
    old_status_display = serializers.CharField(
        source="get_old_status_display", read_only=True
    )
    new_status_display = serializers.CharField(
        source="get_new_status_display", read_only=True
    )
    change_type_display = serializers.CharField(
        source="get_change_type_display", read_only=True
    )
    formatted_date = serializers.ReadOnlyField()

    class Meta:
        model = TaskStatusHistory
        fields = [
            "id",
            "task",
            "old_status",
            "old_status_display",
            "new_status",
            "new_status_display",
            "changed_by",
            "remarks",
            "change_type",
            "change_type_display",
            "related_approval",
            "created_at",
            "formatted_date",
        ]
        read_only_fields = ["id", "created_at"]


class TaskApprovalSerializer(serializers.ModelSerializer):
    """Serializer for TaskApproval model"""

    approver = UserMiniSerializer(read_only=True)
    next_approver = UserMiniSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    created_at = serializers.DateTimeField(
        format="%b %d, %Y at %I:%M %p", read_only=True
    )
    updated_at = serializers.DateTimeField(
        format="%b %d, %Y at %I:%M %p", read_only=True
    )

    class Meta:
        model = TaskApproval
        fields = [
            "id",
            "task",
            "approver",
            "action",
            "action_display",
            "comments",
            "step_number",
            "next_approver",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InitiateApprovalSerializer(serializers.Serializer):
    """Serializer for initiating task approval workflow"""

    approvers = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of user IDs who will approve this task in sequence",
    )

    def validate_approvers(self, value):
        """Validate that all approver IDs are valid admin users"""
        from core.models import User

        # Check that all user IDs exist and are admins
        users = User.objects.filter(id__in=value, role="admin")
        if len(users) != len(value):
            raise serializers.ValidationError(
                "All approvers must be valid admin users."
            )
        return value


class ProcessApprovalSerializer(serializers.Serializer):
    """Serializer for processing approval decisions"""

    ACTION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    action = serializers.ChoiceField(
        choices=ACTION_CHOICES, help_text="The approval decision"
    )
    comments = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional comments about the approval decision",
    )
    next_approver = serializers.IntegerField(
        required=False, help_text="User ID of next approver (optional, for forwarding)"
    )

    def validate_next_approver(self, value):
        """Validate that next_approver is a valid admin user"""
        if value is not None:
            from core.models import User

            try:
                user = User.objects.get(id=value, role="admin")
                return user
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "Next approver must be a valid admin user."
                )
        return None
