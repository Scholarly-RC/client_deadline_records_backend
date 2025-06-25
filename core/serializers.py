from django.utils import timezone
from rest_framework import serializers

from core.models import (
    AppLog,
    Client,
    ClientDeadline,
    ClientDocument,
    DeadlineType,
    Notification,
    User,
    WorkUpdate,
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


class DeadlineTypeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeadlineType
        fields = ["id", "name"]


class ClientDeadlineMiniSerializer(serializers.ModelSerializer):

    class Meta:
        model = ClientDeadline
        fields = ["id", "due_date", "status"]


class ClientDocumentMiniSerializer(serializers.ModelSerializer):
    size = serializers.SerializerMethodField()
    uploaded_by = UserMiniSerializer()

    class Meta:
        model = ClientDocument
        fields = ["id", "name", "file", "size", "uploaded_by", "uploaded_at"]

    def get_size(self, obj):
        if obj.file:
            size_mb = round(obj.file.size / (1024 * 1024), 2)
            return f"{size_mb} MB"
        return None


class WorkUpdateMiniSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = WorkUpdate
        fields = ["id", "status", "notes", "created_at"]


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


class DeadlineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeadlineType
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    created_by = UserMiniSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ClientBirthdaySerializer(serializers.ModelSerializer):
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ["name", "date_of_birth", "days_remaining"]
        read_only_fields = ["created_at", "updated_at"]

    def get_days_remaining(self, obj):
        return (obj.date_of_birth - get_today_local()).days


class ClientDocumentSerializer(serializers.ModelSerializer):
    client = ClientMiniSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), source="client", write_only=True
    )
    deadline = ClientDeadlineMiniSerializer(read_only=True)
    deadline_id = serializers.PrimaryKeyRelatedField(
        queryset=ClientDeadline.objects.all(), source="deadline", write_only=True
    )
    uploaded_by = UserMiniSerializer(read_only=True)
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


class ClientDeadlineSerializer(serializers.ModelSerializer):
    client = ClientMiniSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), source="client", write_only=True
    )
    deadline_type = DeadlineTypeMiniSerializer(read_only=True)
    deadline_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DeadlineType.objects.all(), source="deadline_type", write_only=True
    )
    assigned_to = UserMiniSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_to",
        write_only=True,
        allow_null=True,
    )
    created_by = UserMiniSerializer(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    documents = ClientDocumentMiniSerializer(read_only=True, many=True)
    work_updates = WorkUpdateMiniSerializer(read_only=True, many=True)

    class Meta:
        model = ClientDeadline
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "status"]

    def get_days_remaining(self, obj):
        return (obj.due_date - get_today_local()).days

    def get_is_overdue(self, obj):
        return obj.due_date < get_today_local() and obj.status not in [
            "completed",
            "cancelled",
        ]


class WorkUpdateSerializer(serializers.ModelSerializer):
    deadline = ClientDeadlineMiniSerializer(read_only=True)
    deadline_id = serializers.PrimaryKeyRelatedField(
        queryset=ClientDeadline.objects.all(), source="deadline", write_only=True
    )
    created_by = UserMiniSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = WorkUpdate
        fields = "__all__"
        read_only_fields = ["created_at"]


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
