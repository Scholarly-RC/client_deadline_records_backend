from rest_framework import serializers

from core.models import (
    Client,
    ClientDeadline,
    ClientDocument,
    DeadlineType,
    User,
    WorkUpdate,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "fullname"]


class DeadlineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeadlineType
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ClientDeadlineSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    deadline_type = DeadlineTypeSerializer(read_only=True)
    deadline_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DeadlineType.objects.all(), source="deadline_type", write_only=True
    )
    assigned_to = UserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_to",
        write_only=True,
        allow_null=True,
    )
    created_by = UserSerializer(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ClientDeadline
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "status"]

    def get_days_remaining(self, obj):
        return (obj.due_date - timezone.now().date()).days

    def get_is_overdue(self, obj):
        return obj.due_date < timezone.now().date() and obj.status not in [
            "completed",
            "cancelled",
        ]


class WorkUpdateSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = WorkUpdate
        fields = "__all__"
        read_only_fields = ["created_at"]


class ClientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ClientDocument
        fields = "__all__"
        read_only_fields = ["uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
