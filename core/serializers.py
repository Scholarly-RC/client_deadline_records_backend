from django.utils import timezone
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
        ]

    def validate(self, data):
        if (
            User.objects.filter(
                first_name__iexact=data.get("first_name"),
                middle_name__iexact=data.get("middle_name"),
                last_name__iexact=data.get("last_name"),
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("This user already exists.")

        return data

    def create(self, validated_data):
        password = validated_data.pop("password")

        # Normalize and format name and email fields
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
        user.set_password(password)  # Hash the password securely
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        # Normalize and format name and email fields
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

        # Set other fields if any additional ones exist in validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Securely set a new password if provided
        if password:
            instance.set_password(password)

        instance.save()
        return instance


class DeadlineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeadlineType
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ClientDeadlineSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), source="client", write_only=True
    )
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
    deadline = ClientDeadlineSerializer(read_only=True)
    deadline_id = serializers.PrimaryKeyRelatedField(
        queryset=ClientDeadline.objects.all(), source="deadline", write_only=True
    )
    created_by = UserSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

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
