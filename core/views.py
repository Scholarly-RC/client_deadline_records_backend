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
from core.choices import TaskStatus
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
from core.serializers import (
    AccountingAuditListSerializer,
    AccountingAuditSerializer,
    AppLogSerializer,
    ClientBirthdaySerializer,
    ClientMiniSerializer,
    ClientSerializer,
    ComplianceListSerializer,
    ComplianceSerializer,
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

        return False


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(is_superuser=True).prefetch_related("logs")
    permission_classes = [permissions.IsAuthenticated]
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

    @action(detail=True, methods=["get"], url_path="deadlines-tasks")
    def get_user_deadlines_tasks(self, request, pk=None):
        user = self.get_object()

        compliance_tasks = user.compliances_assigned_to.all()
        financial_statement_preparations = (
            user.financial_statement_preparations_assigned_to.all()
        )
        accounting_audits = user.accounting_audits_assigned_to.all()
        finance_implementations = user.finance_implementations_assigned_to.all()
        human_resource_implementations = (
            user.human_resource_implementations_assigned_to.all()
        )
        miscellaneous_tasks = user.miscellaneous_tasks_assigned_to.all()
        tax_cases = user.tax_cases_assigned_to.all()

        response_data = {
            "compliance": ComplianceListSerializer(compliance_tasks, many=True).data,
            "financial_statement_preparations": FinancialStatementPreparationListSerializer(
                financial_statement_preparations, many=True
            ).data,
            "accounting_audits": AccountingAuditListSerializer(
                accounting_audits, many=True
            ).data,
            "finance_implementations": FinanceImplementationListSerializer(
                finance_implementations, many=True
            ).data,
            "human_resource_implementations": HumanResourceImplementationListSerializer(
                human_resource_implementations, many=True
            ).data,
            "miscellaneous_tasks": MiscellaneousTasksListSerializer(
                miscellaneous_tasks, many=True
            ).data,
            "tax_cases": TaxCaseListSerializer(tax_cases, many=True).data,
        }

        return Response(response_data, status=status.HTTP_200_OK)


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
            queryset = queryset.filter(created_by=self.request.user).distinct()

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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        deadline = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")
            deadline.status = TaskStatus(updated_status).value
            deadline.remarks = updated_remarks
            deadline.save()
            deadline.add_status_update(status=updated_status, remarks=updated_remarks)
            serializer = self.get_serializer(deadline)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StatsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        data = {}
        now = get_now_local()
        today = now.date()
        in_seven_days = today + timedelta(days=7)

        current_user = request.user

        is_admin = current_user.is_admin

        if is_admin:
            total_clients = Client.objects.filter(status="active").count()
            data.update({"total_clients": total_clients})

        return Response(
            data,
            status=status.HTTP_200_OK,
        )


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
