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
    AccountingAudit,
    AppLog,
    Client,
    ClientDeadline,
    ClientDocument,
    Compliance,
    DeadlineType,
    FinanceImplementation,
    FinancialStatementPreparation,
    HumanResourceImplementation,
    MiscellaneousTasks,
    Notification,
    TaxCase,
    User,
    WorkUpdate,
)
from core.serializers import (
    AccountingAuditListSerializer,
    AccountingAuditSerializer,
    AppLogSerializer,
    ClientBirthdaySerializer,
    ClientDeadlineSerializer,
    ClientDocumentSerializer,
    ClientMiniSerializer,
    ClientSerializer,
    ComplianceListSerializer,
    ComplianceSerializer,
    DeadlineTypeSerializer,
    FinanceImplementationListSerializer,
    FinanceImplementationSerializer,
    FinancialStatementPreparationListSerializer,
    FinancialStatementPreparationSerializer,
    HumanResourceImplementationListSerializer,
    HumanResourceImplementationSerializer,
    MiscellaneousTasksListSerializer,
    MiscellaneousTasksSerializer,
    NotificationSerializer,
    TaxCaseListSerializer,
    TaxCaseSerializer,
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

    @action(detail=False, methods=["get"], url_path="users-with-deadlines")
    def get_users_with_deadlines(self, request):
        clients = (
            self.get_queryset().filter(assigned_deadlines__isnull=False).distinct()
        )
        serializer = UserMiniSerializer(clients, many=True)
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
        filters.OrderingFilter,
    ]
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

    @action(detail=False, methods=["get"], url_path="birthdays")
    def get_birthdays(self, request):
        today = get_today_local()
        month = today.month

        monthly_birthdays = self.get_queryset().filter(date_of_birth__month=month)

        birthdays_today = monthly_birthdays.filter(date_of_birth=today)
        upcoming_birthdays = monthly_birthdays.filter(date_of_birth__gt=today)
        past_birthdays = monthly_birthdays.filter(date_of_birth__lt=today)

        return Response(
            {
                "today": ClientBirthdaySerializer(birthdays_today, many=True).data,
                "upcoming": ClientBirthdaySerializer(
                    upcoming_birthdays, many=True
                ).data,
                "past": ClientBirthdaySerializer(past_birthdays, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="client-with-deadlines")
    def get_client_with_deadlines(self, request):
        clients = self.get_queryset().filter(deadlines__isnull=False).distinct()
        serializer = ClientMiniSerializer(clients, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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


class AccountingAuditViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AccountingAudit records

    Provides CRUD operations for accounting audit tasks with filtering,
    searching, and ordering capabilities.
    """

    queryset = AccountingAudit.objects.select_related("assigned_to", "client").all()
    serializer_class = AccountingAuditSerializer
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
        "engagement_date": ["gte", "lte", "exact"],
        "deadline": ["gte", "lte", "exact"],
        "completion_date": ["gte", "lte", "exact"],
    }

    # Search fields
    search_fields = ["description", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "engagement_date",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return AccountingAuditListSerializer
        return AccountingAuditSerializer

    def perform_create(self, serializer):
        """Set last_update timestamp when creating"""
        serializer.save(last_update=timezone.now())

    def perform_update(self, serializer):
        """Set last_update timestamp when updating"""
        serializer.save(last_update=timezone.now())

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get all overdue accounting audit tasks"""
        today = timezone.now().date()
        overdue_tasks = self.get_queryset().filter(
            deadline__lt=today,
            status__in=[
                "NOT_YET_STARTED",
                "IN_PROGRESS",
            ],
        )

        serializer = self.get_serializer(overdue_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def due_soon(self, request):
        """Get accounting audit tasks due within the next 7 days"""
        from datetime import timedelta

        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        due_soon_tasks = self.get_queryset().filter(
            deadline__gte=today,
            deadline__lte=next_week,
            status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
        )

        serializer = self.get_serializer(due_soon_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_user(self, request):
        """Get accounting audit tasks grouped by assigned user"""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_tasks = self.get_queryset().filter(assigned_to_id=user_id)
        serializer = self.get_serializer(user_tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_completed(self, request, pk=None):
        """Mark an accounting audit task as completed"""
        audit = self.get_object()

        completion_date = request.data.get("completion_date", timezone.now().date())
        date_complied = request.data.get("date_complied", timezone.now().date())
        remarks = request.data.get("remarks", audit.remarks)

        audit.status = "COMPLETED"
        audit.completion_date = completion_date
        audit.date_complied = date_complied
        audit.remarks = remarks
        audit.last_update = timezone.now()
        audit.save()

        serializer = self.get_serializer(audit)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get accounting audit statistics"""
        queryset = self.get_queryset()

        stats = {
            "total": queryset.count(),
            "completed": queryset.filter(status="COMPLETED").count(),
            "in_progress": queryset.filter(status="IN_PROGRESS").count(),
            "not_started": queryset.filter(status="NOT_YET_STARTED").count(),
            "overdue": queryset.filter(
                deadline__lt=timezone.now().date(),
                status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
            ).count(),
            "high_priority": queryset.filter(priority="HIGH").count(),
            "medium_priority": queryset.filter(priority="MEDIUM").count(),
            "low_priority": queryset.filter(priority="LOW").count(),
        }

        return Response(stats)


class ComplianceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Compliance records

    Provides CRUD operations for compliance tasks with filtering,
    searching, and ordering capabilities.
    """

    queryset = Compliance.objects.select_related("assigned_to", "client").all()
    serializer_class = ComplianceSerializer
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
        "engagement_date": ["gte", "lte", "exact"],
        "deadline": ["gte", "lte", "exact"],
        "completion_date": ["gte", "lte", "exact"],
    }

    # Search fields
    search_fields = ["description", "steps", "requirements", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "engagement_date",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return ComplianceListSerializer
        return ComplianceSerializer

    def perform_create(self, serializer):
        """Set last_update timestamp when creating"""
        serializer.save(last_update=timezone.now())

    def perform_update(self, serializer):
        """Set last_update timestamp when updating"""
        serializer.save(last_update=timezone.now())

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get all overdue compliance tasks"""
        today = timezone.now().date()
        overdue_tasks = self.get_queryset().filter(
            deadline__lt=today,
            status__in=[
                "NOT_YET_STARTED",
                "IN_PROGRESS",
            ],  # Adjust based on your TaskStatus choices
        )

        serializer = self.get_serializer(overdue_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def due_soon(self, request):
        """Get compliance tasks due within the next 7 days"""
        from datetime import timedelta

        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        due_soon_tasks = self.get_queryset().filter(
            deadline__gte=today,
            deadline__lte=next_week,
            status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
        )

        serializer = self.get_serializer(due_soon_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_user(self, request):
        """Get compliance tasks grouped by assigned user"""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_tasks = self.get_queryset().filter(assigned_to_id=user_id)
        serializer = self.get_serializer(user_tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_completed(self, request, pk=None):
        """Mark a compliance task as completed"""
        compliance = self.get_object()

        completion_date = request.data.get("completion_date", timezone.now().date())
        date_complied = request.data.get("date_complied", timezone.now().date())
        remarks = request.data.get("remarks", compliance.remarks)

        compliance.status = "COMPLETED"  # Adjust based on your TaskStatus choices
        compliance.completion_date = completion_date
        compliance.date_complied = date_complied
        compliance.remarks = remarks
        compliance.last_update = timezone.now()
        compliance.save()

        serializer = self.get_serializer(compliance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get compliance statistics"""
        queryset = self.get_queryset()

        stats = {
            "total": queryset.count(),
            "completed": queryset.filter(status="COMPLETED").count(),
            "in_progress": queryset.filter(status="IN_PROGRESS").count(),
            "not_started": queryset.filter(status="NOT_YET_STARTED").count(),
            "overdue": queryset.filter(
                deadline__lt=timezone.now().date(),
                status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
            ).count(),
            "high_priority": queryset.filter(priority="HIGH").count(),
            "medium_priority": queryset.filter(priority="MEDIUM").count(),
            "low_priority": queryset.filter(priority="LOW").count(),
        }

        return Response(stats)


class FinancialStatementPreparationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing FinancialStatementPreparation records
    """

    queryset = FinancialStatementPreparation.objects.select_related(
        "assigned_to", "client"
    ).all()
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

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return FinancialStatementPreparationListSerializer
        return FinancialStatementPreparationSerializer


class FinanceImplementationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing FinanceImplementation records
    """

    queryset = FinanceImplementation.objects.select_related(
        "assigned_to", "client"
    ).all()
    serializer_class = FinanceImplementationSerializer
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
    search_fields = ["description", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return FinanceImplementationListSerializer
        return FinanceImplementationSerializer


class HumanResourceImplementationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing HumanResourceImplementation records
    """

    queryset = HumanResourceImplementation.objects.select_related(
        "assigned_to", "client"
    ).all()
    serializer_class = HumanResourceImplementationSerializer
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
    search_fields = ["description", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return HumanResourceImplementationListSerializer
        return HumanResourceImplementationSerializer


class MiscellaneousTasksViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MiscellaneousTasks records
    """

    queryset = MiscellaneousTasks.objects.select_related("assigned_to", "client").all()
    serializer_class = MiscellaneousTasksSerializer
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
    search_fields = ["area", "description", "remarks"]

    # Ordering options
    ordering_fields = [
        "deadline",
        "priority",
        "status",
        "last_update",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return MiscellaneousTasksListSerializer
        return MiscellaneousTasksSerializer


class TaxCaseViewSet(viewsets.ModelViewSet):
    queryset = TaxCase.objects.select_related("client", "assigned_to").all()
    serializer_class = TaxCaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        "client": ["exact"],
        "category": ["exact", "in"],
        "type": ["exact", "in"],
        "form": ["exact", "in"],
        "status": ["exact", "in"],
        "priority": ["exact", "in"],
        "assigned_to": ["exact"],
        "engagement_date": ["gte", "lte", "exact"],
        "deadline": ["gte", "lte", "exact"],
        "date_complied": ["gte", "lte", "exact"],
        "completion_date": ["gte", "lte", "exact"],
        "last_update": ["gte", "lte", "exact"],
    }

    search_fields = ["period_covered", "working_paper", "remarks"]

    ordering_fields = [
        "last_followup",
        "tax_payable",
        "status",
        "priority",
        "engagement_date",
        "deadline",
        "date_complied",
        "completion_date",
        "last_update",
    ]
    ordering = ["-last_followup"]  # Default ordering

    def get_serializer_class(self):
        if self.action == "list":
            return TaxCaseListSerializer
        return TaxCaseSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        create_log(self.request.user, f"Created tax case: {instance}.")

    def perform_update(self, serializer):
        instance = serializer.save()
        create_log(self.request.user, f"Updated tax case: {instance}.")


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
