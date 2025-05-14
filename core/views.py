# views.py
import os
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Client,
    ClientDeadline,
    ClientDocument,
    DeadlineType,
    User,
    WorkUpdate,
)
from core.serializers import (
    ClientDeadlineSerializer,
    ClientDocumentSerializer,
    ClientSerializer,
    DeadlineTypeSerializer,
    UserSerializer,
    WorkUpdateSerializer,
)


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or staff to edit it.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        # For objects with created_by field
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user

        # For ClientDeadline with assigned_to field
        if hasattr(obj, "assigned_to"):
            return obj.assigned_to == request.user

        return False


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(is_superuser=True)
    serializer_class = UserSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
    ]
    search_fields = ["first_name", "middle_name", "last_name", "email", "username"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Will trigger validate()
        serializer.save()  # Will trigger create()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="get-current-user")
    def get_current_user(self, request):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="toggle-active-status")
    def toggle_active_status(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="user-choices")
    def get_user_choices(self, request):
        users = self.get_queryset().filter(is_active=True)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
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
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class DeadlineTypeViewSet(viewsets.ModelViewSet):
    queryset = DeadlineType.objects.all()
    serializer_class = DeadlineTypeSerializer
    # permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    # TODO: Implement permissions
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


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
            "client", "deadline_type", "assigned_to", "created_by"
        )

        # Non-staff users only see deadlines they created or are assigned to
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(assigned_to=self.request.user)
            )

        # Filter for upcoming deadlines
        upcoming = self.request.query_params.get("upcoming", None)
        if upcoming is not None:
            queryset = queryset.filter(due_date__gte=timezone.now().date())

        # Filter for overdue deadlines
        overdue = self.request.query_params.get("overdue", None)
        if overdue is not None:
            queryset = queryset.filter(
                due_date__lt=timezone.now().date(),
                status__in=["pending", "in_progress"],
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="upcoming-deadlines")
    def get_upcoming_deadlines(self, request):
        today = timezone.now().date()
        in_seven_days = today + timedelta(days=7)
        deadlines = self.get_queryset().filter(
            status__in=["in_progress", "pending"],
            due_date__gte=today,
            due_date__lte=in_seven_days,
        )
        serializer = ClientDeadlineSerializer(deadlines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        deadline = serializer.save()
        deadline.work_updates.all().delete()
        deadline.status = "pending"
        deadline.save()


class WorkUpdateViewSet(viewsets.ModelViewSet):
    serializer_class = WorkUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = WorkUpdate.objects.select_related("deadline", "created_by")

        # Filter by deadline if provided
        deadline_id = self.request.query_params.get("deadline", None)
        if deadline_id is not None:
            queryset = queryset.filter(deadline_id=deadline_id)

        # Non-staff users only see updates they created or for deadlines they're assigned to
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(created_by=self.request.user)
                | Q(deadline__assigned_to=self.request.user)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

        # Update the deadline status if it's changed in the update
        deadline = serializer.validated_data["deadline"]
        new_status = serializer.validated_data["status"]
        if deadline.status != new_status:
            deadline.status = new_status
            if new_status == "completed":
                deadline.completed_at = timezone.now()
            else:
                deadline.completed_at = None
            deadline.save()


class ClientDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = ClientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = ClientDocument.objects.select_related("client", "uploaded_by")

        # Filter by client if provided
        client_id = self.request.query_params.get("client", None)
        if client_id is not None:
            queryset = queryset.filter(client_id=client_id)

        # Non-staff users only see documents they uploaded or for clients they created
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(uploaded_by=self.request.user)
                | Q(client__created_by=self.request.user)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class StatsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        now = timezone.now()
        today = now.date()
        in_seven_days = today + timedelta(days=7)

        total_clients = Client.objects.filter(status="active").count()
        overdue_deadlines = ClientDeadline.objects.filter(status="overdue").count()
        monthly_completed_deadlines = ClientDeadline.objects.filter(
            status="completed", due_date__month=now.month
        ).count()

        upcoming_deadlines = ClientDeadline.objects.filter(
            status__in=["in_progress", "pending"],
            due_date__gte=today,
            due_date__lte=in_seven_days,
        ).count()

        pending_deadlines = ClientDeadline.objects.filter(status="pending").count()
        cancelled_deadlines = ClientDeadline.objects.filter(status="cancelled").count()

        return Response(
            {
                "total_clients": total_clients,
                "overdue_deadlines": overdue_deadlines,
                "monthly_completed_deadlines": monthly_completed_deadlines,
                "upcoming_deadlines": upcoming_deadlines,
                "pending_deadlines": pending_deadlines,
                "cancelled_deadlines": cancelled_deadlines,
            },
            status=status.HTTP_200_OK,
        )


def download_client_document(request, file_id):
    # TODO: Implement permissions
    try:
        client_document = ClientDocument.objects.get(id=file_id)
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
