# views.py
import os
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.deletion import RestrictedError
from django.http import FileResponse, Http404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.actions import create_log, create_notifications
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
from core.serializers import (
    AppLogSerializer,
    ClientDeadlineSerializer,
    ClientDocumentSerializer,
    ClientSerializer,
    DeadlineTypeSerializer,
    NotificationSerializer,
    UserMiniSerializer,
    UserSerializer,
    WorkUpdateSerializer,
)
from core.utils import (
    get_admin_users,
    get_notification_recipients,
    get_now_local,
    get_today_local,
)


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or staff to edit it.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True

        # For objects with created_by field
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user

        # For ClientDeadline with assigned_to field
        if hasattr(obj, "assigned_to"):
            return obj.assigned_to == request.user

        return False


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(is_superuser=True).prefetch_related("logs")
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    serializer_class = UserSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
    ]
    search_fields = ["first_name", "middle_name", "last_name", "email", "username"]

    def perform_create(self, serializer):
        instance = serializer.save()
        create_log(self.request.user, f"Created user: {instance}.")

    def perform_update(self, serializer):
        instance = serializer.save()
        create_log(
            self.request.user,
            f"Updated user: {instance}. Password changed: {'Yes' if 'password' in serializer.validated_data else 'No'}.",
        )

    @action(detail=False, methods=["get"], url_path="get-current-user")
    def get_current_user(self, request):
        user = request.user
        serializer = UserMiniSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="toggle-active-status")
    def toggle_active_status(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        serializer = self.get_serializer(user)
        create_log(
            request.user,
            f"{'Enabled' if user.is_active else 'Disabled'} user: {user.fullname}.",
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="user-choices")
    def get_user_choices(self, request):
        users = self.get_queryset().filter(is_active=True)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="unread-notification-count")
    def get_unread_notification_count(self, request, pk=None):
        unread_count = self.get_object().notifications.filter(is_read=False).count()
        return Response({"unread_count": unread_count}, status=status.HTTP_200_OK)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.select_related("created_by")
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status"]
    search_fields = ["name", "contact_person", "email", "address", "phone"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Non-staff users only see clients they created
        if not self.request.user.is_admin:
            queryset = queryset.filter(
                deadlines__assigned_to=self.request.user
            ).distinct()

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            create_log(self.request.user, f"Deleted client: {instance}.")
        except RestrictedError as e:
            return Response(
                {
                    "detail": "Cannot delete this object because it is referenced by other records.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        create_log(self.request.user, f"Created client: {instance}.")

    def perform_update(self, serializer):
        instance = serializer.save()
        create_log(
            self.request.user,
            f"Updated client: {instance}. Status: {'Active' if instance.is_active else 'Inactive'}.",
        )


class DeadlineTypeViewSet(viewsets.ModelViewSet):
    queryset = DeadlineType.objects.all()
    serializer_class = DeadlineTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            create_log(self.request.user, f"Deleted deadline type: {instance}.")
        except RestrictedError as e:
            return Response(
                {
                    "detail": "Cannot delete this object because it is referenced by other records.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        instance = serializer.save()
        create_log(self.request.user, f"Created deadline type: {instance}.")

    def perform_update(self, serializer):
        instance = serializer.save()
        create_log(self.request.user, f"Updated deadline type: {instance}.")


class ClientDeadlineViewSet(viewsets.ModelViewSet):
    serializer_class = ClientDeadlineSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["client", "deadline_type", "status", "priority", "assigned_to"]
    search_fields = ["description", "client__name", "deadline_type__name"]
    ordering_fields = ["due_date", "priority", "created_at"]

    def get_queryset(self):
        queryset = ClientDeadline.objects.select_related(
            "assigned_to",
            "created_by",
            "client",
            "deadline_type",
        ).prefetch_related(
            "documents",
            "work_updates",
        )

        # Non-staff users only see deadlines they created or are assigned to
        if not self.request.user.is_admin:
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(assigned_to=self.request.user)
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="upcoming-deadlines")
    def get_upcoming_deadlines(self, request):
        today = get_today_local()
        in_seven_days = today + timedelta(days=7)
        deadlines = self.get_queryset().filter(
            status__in=["in_progress", "pending"],
            due_date__gte=today,
            due_date__lte=in_seven_days,
        )
        serializer = ClientDeadlineSerializer(deadlines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            create_log(self.request.user, f"Deleted deadline: {instance}.")

            for user in get_notification_recipients(instance.deadline):
                if user != self.request.user:
                    create_notifications(
                        recipient=user,
                        title="Deadline Removed",
                        message=f"The deadline has been removed. ({instance.deadline}).",
                        link=f"/deadlines/{instance.deadline.id}",
                    )
        except Exception as e:
            return Response(
                {
                    "detail": "An unexpected error occurred during deletion.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        create_log(self.request.user, f"Created deadline: {instance}.")
        create_notifications(
            recipient=instance.assigned_to,
            title="New Deadline Assigned",
            message=f"New deadline assigned to you: {instance}.",
            link=f"/deadlines/{instance.id}",
        )

    def perform_update(self, serializer):
        current_assignee = self.get_object().assigned_to
        submitted_assignee = serializer.validated_data["assigned_to"]
        new_assignee = current_assignee != submitted_assignee

        deadline = serializer.save()
        deadline.work_updates.all().delete()
        deadline.status = "pending"
        deadline.save()
        create_log(self.request.user, f"Updated deadline: {deadline}.")

        if new_assignee:
            create_notifications(
                recipient=submitted_assignee,
                title="Deadline Assignment Update",
                message=f"You have been assigned to this deadline: {deadline}.",
                link=f"/deadlines/{deadline.id}",
            )
            create_notifications(
                recipient=current_assignee,
                title="Deadline Assignment Update",
                message=f"Assignment removed for deadline: {deadline}.",
                link=f"/deadlines/{deadline.id}",
            )
            for user in get_admin_users():
                if user != self.request.user:
                    create_notifications(
                        recipient=user,
                        title="Deadline Modified",
                        message=f"Deadline has been updated: {deadline}.",
                        link=f"/deadlines/{deadline.id}",
                    )
        else:
            for user in get_notification_recipients(deadline):
                if user != self.request.user:
                    create_notifications(
                        recipient=user,
                        title="Deadline Modified",
                        message=f"Deadline has been updated: {deadline}.",
                        link=f"/deadlines/{deadline.id}",
                    )


class WorkUpdateViewSet(viewsets.ModelViewSet):
    serializer_class = WorkUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = WorkUpdate.objects.select_related("created_by", "deadline")

        # Non-staff users only see updates they created or for deadlines they're assigned to
        if not self.request.user.is_admin:
            queryset = queryset.filter(
                Q(created_by=self.request.user)
                | Q(deadline__assigned_to=self.request.user)
            )

        return queryset

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        # Update the deadline status if it's changed in the update
        deadline = serializer.validated_data["deadline"]
        new_status = serializer.validated_data["status"]
        if deadline.status != new_status:
            deadline.status = new_status
            if new_status == "completed":
                deadline.completed_at = get_now_local()
            else:
                deadline.completed_at = None
            deadline.save()

        create_log(
            self.request.user,
            f"Created work update: {instance}. Instance: {instance.get_status_display()}.",
        )

        for user in get_notification_recipients(instance.deadline):
            if user != self.request.user:
                create_notifications(
                    recipient=user,
                    title="Deadline Update Posted",
                    message=f"New update added to deadline: {instance.deadline}.",
                    link=f"/deadlines/{instance.deadline.id}",
                )


class ClientDocumentViewSet(viewsets.ModelViewSet):
    queryset = ClientDocument.objects.select_related(
        "client", "deadline", "uploaded_by"
    )

    serializer_class = ClientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        instance = serializer.save(uploaded_by=self.request.user)
        create_log(self.request.user, f"Uploaded client document: {instance}.")

        for user in get_notification_recipients(instance.deadline):
            if user != self.request.user:
                create_notifications(
                    recipient=user,
                    title="New File Added",
                    message=f"A file has been uploaded for deadline: {instance.deadline}.",
                    link=f"/deadlines/{instance.deadline.id}",
                )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            create_log(self.request.user, f"Deleted an uploaded file: {instance}.")

            for user in get_notification_recipients(instance.deadline):
                if user != self.request.user:
                    create_notifications(
                        recipient=user,
                        title="File Removed",
                        message=f"A file has been removed from deadline: {instance.deadline}.",
                        link=f"/deadlines/{instance.deadline.id}",
                    )
        except Exception as e:
            return Response(
                {
                    "detail": "An unexpected error occurred during deletion.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StatsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        data = {}
        now = get_now_local()
        today = now.date()
        in_seven_days = today + timedelta(days=7)

        current_user = request.user

        is_admin = current_user.is_admin

        client_deadline = ClientDeadline.objects.all()

        if is_admin:
            total_clients = Client.objects.filter(status="active").count()
            data.update({"total_clients": total_clients})
        else:
            client_deadline = client_deadline.filter(assigned_to=current_user)

        overdue_deadlines = client_deadline.filter(status="overdue").count()
        monthly_completed_deadlines = client_deadline.filter(
            status="completed", due_date__month=now.month
        ).count()

        upcoming_deadlines = client_deadline.filter(
            status__in=["in_progress", "pending"],
            due_date__gte=today,
            due_date__lte=in_seven_days,
        ).count()

        pending_deadlines = client_deadline.filter(status="pending").count()
        cancelled_deadlines = client_deadline.filter(status="cancelled").count()

        data.update(
            {
                "overdue_deadlines": overdue_deadlines,
                "monthly_completed_deadlines": monthly_completed_deadlines,
                "upcoming_deadlines": upcoming_deadlines,
                "pending_deadlines": pending_deadlines,
                "cancelled_deadlines": cancelled_deadlines,
            }
        )

        return Response(
            data,
            status=status.HTTP_200_OK,
        )


def download_client_document(request, file_id):
    try:
        client_document = ClientDocument.objects.get(id=file_id)
        if client_document.uploaded_by != request.user and not request.user.is_admin:
            raise PermissionDenied("Permission denied.")
    except ClientDocument.DoesNotExist:
        raise Http404("File not found")

    file_path = client_document.file.path

    if not os.path.exists(file_path):
        raise Http404("File does not exist on disk")

    response = FileResponse(open(file_path, "rb"))
    response["Content-Disposition"] = (
        f'attachment; filename="{os.path.basename(file_path)}"'
    )
    return response


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.select_related("recipient")
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
    ]

    filterset_fields = ["recipient", "is_read"]

    @action(detail=True, methods=["post"], url_path="mark-as-read")
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response(status=status.HTTP_200_OK)


class AppLogViewSet(viewsets.ModelViewSet):
    queryset = AppLog.objects.select_related("user")
    serializer_class = AppLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    filter_backends = [
        DjangoFilterBackend,
    ]
    filterset_fields = ["user"]

    @action(detail=False, methods=["get"], url_path="users")
    def get_user_choices(self, request):
        users = User.objects.exclude(logs__isnull=True)
        serializer = UserMiniSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
