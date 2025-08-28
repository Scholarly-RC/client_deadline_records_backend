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

from core.actions import (
    create_log,
    create_notifications,
    initiate_task_approval,
    process_task_approval,
)
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
from core.pagination import CustomPageNumberPagination
from core.serializers import (
    AppLogSerializer,
    ClientBirthdaySerializer,
    ClientSerializer,
    InitiateApprovalSerializer,
    NotificationSerializer,
    ProcessApprovalSerializer,
    TaskApprovalSerializer,
    TaskListSerializer,
    TaskSerializer,
    TaskStatusHistorySerializer,
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

        # Get all tasks assigned to this user
        tasks = user.tasks_assigned_to.all()

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginated_tasks = paginator.paginate_queryset(tasks, request)

        # Serialize the paginated data
        serializer = TaskListSerializer(paginated_tasks, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Task records

    Provides CRUD operations for tasks with filtering,
    searching, and ordering capabilities.
    """

    queryset = (
        Task.objects.select_related("assigned_to", "client")
        .prefetch_related(
            "approvals__approver",
            "approvals__next_approver",
            "status_history_records__changed_by",
        )
        .all()
    )
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Filtering options
    filterset_fields = {
        "client": ["exact"],
        "category": ["exact", "in"],
        "status": ["exact", "in"],
        "priority": ["exact", "in"],
        "assigned_to": ["exact"],
        "engagement_date": ["gte", "lte", "exact"],
        "deadline": ["gte", "lte", "exact"],
        "completion_date": ["gte", "lte", "exact"],
        "tax_category": ["exact", "in"],
        "tax_type": ["exact", "in"],
        "form": ["exact", "in"],
    }

    # Search fields
    search_fields = [
        "description",
        "remarks",
        "steps",
        "requirements",
        "type",
        "needed_data",
        "area",
        "working_paper",
    ]

    # Ordering options
    ordering_fields = [
        "deadline",
        "engagement_date",
        "priority",
        "status",
        "last_update",
        "tax_payable",
        "last_followup",
    ]
    ordering = ["-last_update"]  # Default ordering

    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        Admin users see all records, non-admin users only see records assigned to them.
        """
        queryset = (
            Task.objects.select_related("assigned_to", "client")
            .prefetch_related(
                "approvals__approver",
                "approvals__next_approver",
                "status_history_records__changed_by",
            )
            .all()
        )

        # Return empty queryset for unauthenticated users
        if not self.request.user.is_authenticated:
            return queryset.none()

        if self.request.user.is_admin:
            return queryset

        return queryset.filter(assigned_to=self.request.user)

    def get_serializer_class(self):
        """Use different serializer for list action"""
        if self.action == "list":
            return TaskListSerializer
        return TaskSerializer

    def perform_create(self, serializer):
        """Set last_update timestamp when creating"""
        instance = serializer.save(last_update=get_now_local())
        create_log(self.request.user, f"Created task: {instance}.")

        # Notify assigned user if task is assigned
        if instance.assigned_to and instance.assigned_to != self.request.user:
            create_notifications(
                recipient=instance.assigned_to,
                title="New Task Assigned",
                message=f"A new task '{instance.description}' has been assigned to you.",
                link="/my-deadlines",
            )

    def update(self, request, *args, **kwargs):
        """Override update to track assigned_to changes"""
        # Get the instance before update
        instance = self.get_object()
        original_assigned_to = instance.assigned_to

        # Perform the update
        response = super().update(request, *args, **kwargs)

        # Get the updated instance
        updated_instance = self.get_object()

        # Check if assigned_to has changed and notify new assignee
        if (
            original_assigned_to != updated_instance.assigned_to
            and updated_instance.assigned_to
            and updated_instance.assigned_to != self.request.user
        ):
            create_notifications(
                recipient=updated_instance.assigned_to,
                title=(
                    "Task Reassigned" if original_assigned_to else "New Task Assigned"
                ),
                message=f"The task '{updated_instance.description}' has been {'reassigned' if original_assigned_to else 'assigned'} to you.",
                link="/my-deadlines",
            )

        return response

    def perform_update(self, serializer):
        """Set last_update timestamp when updating"""
        serializer.save(last_update=get_now_local())
        create_log(self.request.user, f"Updated task: {serializer.instance}.")

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get all overdue tasks"""
        today = get_today_local()
        overdue_tasks = self.get_queryset().filter(
            deadline__lt=today,
            status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
        )

        serializer = self.get_serializer(overdue_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def due_soon(self, request):
        """Get tasks due within the next 7 days"""
        today = get_today_local()
        next_week = today + timedelta(days=7)

        due_soon_tasks = self.get_queryset().filter(
            deadline__gte=today,
            deadline__lte=next_week,
            status__in=["NOT_YET_STARTED", "IN_PROGRESS"],
        )

        serializer = self.get_serializer(due_soon_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get tasks grouped by category"""
        category = request.query_params.get("category")
        if not category:
            return Response(
                {"error": "category parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category_tasks = self.get_queryset().filter(category=category)
        serializer = self.get_serializer(category_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_user(self, request):
        """Get tasks grouped by assigned user"""
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
        """Mark a task as completed"""
        task = self.get_object()

        completion_date = request.data.get("completion_date", get_today_local())
        date_complied = request.data.get("date_complied", get_today_local())
        remarks = request.data.get("remarks", task.remarks)

        task.status = TaskStatus.COMPLETED.value
        task.completion_date = completion_date
        task.date_complied = date_complied
        task.remarks = remarks
        task.last_update = get_now_local()
        task.save()

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get comprehensive task statistics optimized for dashboard visualization"""
        from django.db.models import Count, Avg, Q, Sum, Case, When, IntegerField, F
        from django.db.models.functions import Extract, TruncMonth
        from datetime import datetime, timedelta
        from core.choices import TaskCategory, TaskStatus, TaskPriority, TaxCaseCategory, TypeOfTaxCase
        
        queryset = self.get_queryset()
        today = get_today_local()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)
        
        # Basic counts with corrected status references
        basic_stats = {
            "total": queryset.count(),
            "completed": queryset.filter(status=TaskStatus.COMPLETED).count(),
            "in_progress": queryset.filter(status=TaskStatus.ON_GOING).count(),
            "pending": queryset.filter(status=TaskStatus.PENDING).count(),
            "for_checking": queryset.filter(status=TaskStatus.FOR_CHECKING).count(),
            "for_revision": queryset.filter(status=TaskStatus.FOR_REVISION).count(),
            "not_started": queryset.filter(status=TaskStatus.NOT_YET_STARTED).count(),
            "cancelled": queryset.filter(status=TaskStatus.CANCELLED).count(),
        }
        
        # Priority distribution
        priority_stats = {
            "high_priority": queryset.filter(priority=TaskPriority.HIGH).count(),
            "medium_priority": queryset.filter(priority=TaskPriority.MEDIUM).count(),
            "low_priority": queryset.filter(priority=TaskPriority.LOW).count(),
        }
        
        # Category distribution with display names
        category_stats = queryset.values('category').annotate(
            count=Count('category')
        ).order_by('-count')
        category_distribution = {}
        for item in category_stats:
            # Get display name for category
            category_display = dict(TaskCategory.choices).get(item['category'], item['category'])
            category_distribution[item['category']] = {
                "count": item['count'],
                "display_name": category_display
            }
        
        # Time-based analysis
        overdue_tasks = queryset.filter(
            deadline__lt=today,
            status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
        ).count()
        
        due_today = queryset.filter(
            deadline=today,
            status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
        ).count()
        
        due_this_week = queryset.filter(
            deadline__range=[today, today + timedelta(days=7)],
            status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
        ).count()
        
        due_this_month = queryset.filter(
            deadline__range=[today, today + timedelta(days=30)],
            status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
        ).count()
        
        # Recent activity metrics - using last_update as proxy for creation
        created_last_week = queryset.filter(last_update__gte=week_ago).count()
        completed_last_week = queryset.filter(
            completion_date__gte=week_ago,
            status=TaskStatus.COMPLETED
        ).count()
        completed_last_month = queryset.filter(
            completion_date__gte=month_ago,
            status=TaskStatus.COMPLETED
        ).count()
        
        # Client distribution (Top 10 clients)
        client_stats = queryset.values(
            'client__name', 'client__id', 'client__status'
        ).annotate(
            total_tasks=Count('id'),
            completed_tasks=Count(Case(
                When(status=TaskStatus.COMPLETED, then=1),
                output_field=IntegerField()
            )),
            overdue_tasks=Count(Case(
                When(
                    Q(deadline__lt=today) & 
                    Q(status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]),
                    then=1
                ),
                output_field=IntegerField()
            )),
            pending_tasks=Count(Case(
                When(status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING], then=1),
                output_field=IntegerField()
            ))
        ).order_by('-total_tasks')[:10]
        
        # Add completion rate for clients
        for client in client_stats:
            if client['total_tasks'] > 0:
                client['completion_rate'] = round((client['completed_tasks'] / client['total_tasks']) * 100, 2)
            else:
                client['completion_rate'] = 0
        
        # User performance with enhanced metrics
        user_stats = queryset.values(
            'assigned_to__first_name', 
            'assigned_to__last_name',
            'assigned_to__id',
            'assigned_to__role'
        ).annotate(
            total_tasks=Count('id'),
            completed_tasks=Count(Case(
                When(status=TaskStatus.COMPLETED, then=1),
                output_field=IntegerField()
            )),
            overdue_tasks=Count(Case(
                When(
                    Q(deadline__lt=today) & 
                    Q(status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]),
                    then=1
                ),
                output_field=IntegerField()
            )),
            pending_tasks=Count(Case(
                When(status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING], then=1),
                output_field=IntegerField()
            )),
            high_priority_tasks=Count(Case(
                When(priority=TaskPriority.HIGH, then=1),
                output_field=IntegerField()
            ))
        ).order_by('-total_tasks')
        
        # Enhanced user stats with calculated metrics
        for user in user_stats:
            total = user['total_tasks']
            if total > 0:
                user['completion_rate'] = round((user['completed_tasks'] / total) * 100, 2)
                user['overdue_rate'] = round((user['overdue_tasks'] / total) * 100, 2)
            else:
                user['completion_rate'] = 0
                user['overdue_rate'] = 0
            user['fullname'] = f"{user['assigned_to__first_name']} {user['assigned_to__last_name']}"
            user['is_admin'] = user['assigned_to__role'] == 'admin'
        
        # Weekly completion trend (last 8 weeks for better chart visualization)
        weekly_trends = []
        for i in range(8):
            week_start = today - timedelta(days=(i * 7) + today.weekday())
            week_end = week_start + timedelta(days=6)
            
            week_completed = queryset.filter(
                completion_date__range=[week_start, week_end],
                status=TaskStatus.COMPLETED
            ).count()
            
            week_created = queryset.filter(
                last_update__range=[week_start, week_end]
            ).count()
            
            weekly_trends.append({
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_label": f"Week of {week_start.strftime('%b %d')}",
                "completed": week_completed,
                "created": week_created
            })
        
        weekly_trends.reverse()  # Show chronologically
        
        # Approval workflow statistics
        approval_stats = {
            "tasks_requiring_approval": queryset.filter(requires_approval=True).count(),
            "tasks_in_approval": queryset.filter(
                requires_approval=True,
                status=TaskStatus.FOR_CHECKING
            ).count(),
            "tasks_approved": queryset.filter(
                requires_approval=True,
                status=TaskStatus.COMPLETED
            ).count(),
            "pending_my_approval": 0  # Will be calculated for current user
        }
        
        # Calculate pending approvals for current user if admin
        if request.user.is_admin:
            from core.models import TaskApproval
            approval_stats["pending_my_approval"] = TaskApproval.objects.filter(
                approver=request.user,
                action="pending"
            ).count()
        
        # Tax-specific analytics
        tax_stats = {}
        tax_tasks = queryset.filter(category=TaskCategory.TAX_CASE)
        if tax_tasks.exists():
            total_payable = tax_tasks.aggregate(total=Sum('tax_payable'))['total'] or 0
            
            tax_stats = {
                "total_tax_cases": tax_tasks.count(),
                "completed_tax_cases": tax_tasks.filter(status=TaskStatus.COMPLETED).count(),
                "tax_payable_total": float(total_payable),
                "average_tax_payable": float(total_payable / tax_tasks.count()) if tax_tasks.count() > 0 else 0,
                "by_tax_category": [
                    {
                        "category": item['tax_category'],
                        "display_name": dict(TaxCaseCategory.choices).get(item['tax_category'], item['tax_category']) if item['tax_category'] else "Not Specified",
                        "count": item['count']
                    }
                    for item in tax_tasks.values('tax_category').annotate(count=Count('tax_category'))
                    if item['tax_category']
                ],
                "by_tax_type": [
                    {
                        "type": item['tax_type'],
                        "display_name": dict(TypeOfTaxCase.choices).get(item['tax_type'], item['tax_type']) if item['tax_type'] else "Not Specified",
                        "count": item['count']
                    }
                    for item in tax_tasks.values('tax_type').annotate(count=Count('tax_type'))
                    if item['tax_type']
                ]
            }
        
        # Productivity and performance metrics
        completed_tasks = queryset.filter(status=TaskStatus.COMPLETED)
        total_tasks = queryset.count()
        
        productivity_stats = {
            "overall_completion_rate": round((basic_stats["completed"] / total_tasks * 100) if total_tasks > 0 else 0, 2),
            "on_time_completion_rate": 0,
            "average_completion_days": 0,
            "tasks_completed_early": 0,
            "tasks_completed_late": 0,
            "workload_balance_score": 0  # How evenly distributed tasks are among users
        }
        
        if completed_tasks.exists():
            # On-time completion rate
            on_time_completed = completed_tasks.filter(
                completion_date__lte=F('deadline')
            ).count()
            late_completed = completed_tasks.filter(
                completion_date__gt=F('deadline')
            ).count()
            early_completed = completed_tasks.filter(
                completion_date__lt=F('deadline')
            ).count()
            
            productivity_stats.update({
                "on_time_completion_rate": round((on_time_completed / completed_tasks.count()) * 100, 2),
                "tasks_completed_early": early_completed,
                "tasks_completed_late": late_completed,
            })
            
            # Average completion time calculation - using engagement_date if available
            completed_with_dates = completed_tasks.filter(
                completion_date__isnull=False,
                engagement_date__isnull=False
            )
            
            if completed_with_dates.exists():
                total_days = sum([
                    (task.completion_date - task.engagement_date).days
                    for task in completed_with_dates
                    if task.completion_date and task.engagement_date
                ])
                if completed_with_dates.count() > 0:
                    productivity_stats["average_completion_days"] = round(total_days / completed_with_dates.count(), 1)
        
        # Calculate workload balance (standard deviation of task distribution)
        if user_stats:
            task_counts = [user['total_tasks'] for user in user_stats]
            if len(task_counts) > 1:
                mean_tasks = sum(task_counts) / len(task_counts)
                variance = sum((x - mean_tasks) ** 2 for x in task_counts) / len(task_counts)
                std_deviation = variance ** 0.5
                # Convert to a 0-100 scale where 100 is perfectly balanced
                productivity_stats["workload_balance_score"] = max(0, round(100 - (std_deviation / mean_tasks * 100), 2)) if mean_tasks > 0 else 100
        
        # System health metrics
        system_health = {
            "active_clients": queryset.values('client').filter(client__status='active').distinct().count(),
            "total_clients": queryset.values('client').distinct().count(),
            "average_tasks_per_client": round(total_tasks / queryset.values('client').distinct().count(), 2) if queryset.values('client').distinct().count() > 0 else 0,
            "critical_overdue": queryset.filter(
                deadline__lt=today - timedelta(days=7),
                priority=TaskPriority.HIGH,
                status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
            ).count(),
            "system_load_indicator": "low"  # Will be calculated based on various factors
        }
        
        # Calculate system load indicator
        overdue_percentage = (overdue_tasks / total_tasks * 100) if total_tasks > 0 else 0
        if overdue_percentage > 20 or system_health["critical_overdue"] > 5:
            system_health["system_load_indicator"] = "high"
        elif overdue_percentage > 10 or system_health["critical_overdue"] > 2:
            system_health["system_load_indicator"] = "medium"
        
        # Quick actions data (useful for dashboard widgets)
        quick_actions = {
            "tasks_need_attention": queryset.filter(
                Q(deadline__lte=today + timedelta(days=3)) &
                Q(status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING])
            ).count(),
            "high_priority_pending": queryset.filter(
                priority=TaskPriority.HIGH,
                status__in=[TaskStatus.NOT_YET_STARTED, TaskStatus.ON_GOING, TaskStatus.PENDING]
            ).count(),
            "recent_completions": completed_last_week,
            "new_tasks_this_week": created_last_week
        }
        
        # Compile comprehensive dashboard statistics
        dashboard_stats = {
            "summary": {
                **basic_stats,
                **priority_stats,
                "overdue": overdue_tasks,
                "due_today": due_today,
                "due_this_week": due_this_week,
                "due_this_month": due_this_month,
            },
            "charts_data": {
                "category_distribution": category_distribution,
                "weekly_trends": weekly_trends,
                "status_breakdown": {
                    "completed": basic_stats["completed"],
                    "in_progress": basic_stats["in_progress"],
                    "pending": basic_stats["pending"],
                    "not_started": basic_stats["not_started"],
                    "for_checking": basic_stats["for_checking"],
                    "for_revision": basic_stats["for_revision"],
                },
                "priority_breakdown": priority_stats
            },
            "performance_metrics": productivity_stats,
            "team_analytics": {
                "user_performance": list(user_stats),
                "workload_distribution": [
                    {"user": user['fullname'], "tasks": user['total_tasks'], "completion_rate": user['completion_rate']}
                    for user in user_stats[:5]  # Top 5 for widget display
                ]
            },
            "client_insights": {
                "top_clients": list(client_stats)[:5],  # Top 5 for dashboard
                "all_clients": list(client_stats)  # Full list for detailed view
            },
            "business_intelligence": {
                "approval_workflow": approval_stats,
                "tax_analysis": tax_stats,
                "system_health": system_health,
                "recent_activity": {
                    "completed_last_week": completed_last_week,
                    "completed_last_month": completed_last_month,
                    "created_last_week": created_last_week
                }
            },
            "quick_actions": quick_actions,
            "metadata": {
                "generated_at": today.isoformat(),
                "user_role": request.user.role,
                "is_admin": request.user.is_admin,
                "data_scope": "all_tasks" if request.user.is_admin else "assigned_tasks"
            }
        }
        
        return Response(dashboard_stats)

    @action(detail=True, methods=["POST"], url_path="update-deadline")
    def update_deadline(self, request, pk=None):
        task = self.get_object()
        try:
            updated_status = request.data.get("status")
            updated_remarks = request.data.get("remarks")

            # Update task fields
            if updated_remarks:
                task.remarks = updated_remarks

            # Use add_status_update to handle both status and remarks updates
            # The method now has built-in logic to prevent unnecessary status history entries
            task.add_status_update(
                new_status=updated_status,
                remarks=updated_remarks,
                changed_by=request.user,
            )

            serializer = TaskListSerializer(task)
            return Response(
                data=serializer.data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"message": f"Something went wrong. {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"], url_path="initiate-approval")
    def initiate_approval(self, request, pk=None):
        """Initiate approval workflow for a task"""
        task = self.get_object()

        # Check if user has permission to initiate approval
        if not request.user.is_admin and task.assigned_to != request.user:
            return Response(
                {
                    "error": "You don't have permission to initiate approval for this task."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if task is already in approval workflow
        if task.requires_approval:
            return Response(
                {"error": "This task is already in approval workflow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate request data
        serializer = InitiateApprovalSerializer(data=request.data)
        if serializer.is_valid():
            approver_ids = serializer.validated_data["approvers"]
            approvers = User.objects.filter(id__in=approver_ids, role="admin")

            try:
                initiate_task_approval(task, list(approvers), request.user)
                return Response(
                    {"message": "Approval workflow initiated successfully."},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to initiate approval workflow: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["POST"], url_path="process-approval")
    def process_approval(self, request, pk=None):
        """Process an approval decision for a task"""
        task = self.get_object()

        # Check if user is an admin
        if not request.user.is_admin:
            return Response(
                {"error": "Only admin users can process approvals."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if task is in approval workflow
        if not task.requires_approval:
            return Response(
                {"error": "This task is not in approval workflow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user is the current approver
        current_approval = TaskApproval.objects.filter(
            task=task,
            approver=request.user,
            step_number=task.current_approval_step,
            action="pending",
        ).first()

        if not current_approval:
            return Response(
                {"error": "You are not the current approver for this task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request data
        serializer = ProcessApprovalSerializer(data=request.data)
        if serializer.is_valid():
            action = serializer.validated_data["action"]
            comments = serializer.validated_data.get("comments", "")
            next_approver = serializer.validated_data.get("next_approver")

            try:
                process_task_approval(
                    task, request.user, action, comments, next_approver
                )
                return Response(
                    {"message": f"Task {action} successfully."},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to process approval: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["GET"], url_path="status-history")
    def status_history(self, request, pk=None):
        """Get status history for a specific task"""
        task = self.get_object()

        # Get all status history records for this task, ordered by creation date
        status_history = TaskStatusHistory.objects.filter(task=task).order_by(
            "-created_at"
        )

        # Serialize the status history records
        serializer = TaskStatusHistorySerializer(status_history, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["GET"], url_path="task-approvals")
    def task_approvals(self, request, pk=None):
        """Get approval records for a specific task"""
        task = self.get_object()

        # Get all approval records for this task, ordered by step number
        approvals = TaskApproval.objects.filter(task=task).order_by("step_number")

        # Serialize the approval records
        serializer = TaskApprovalSerializer(approvals, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["GET"], url_path="pending-approvals")
    def pending_approvals(self, request):
        """Get tasks pending current user's approval"""
        if not request.user.is_admin:
            return Response(
                {"error": "Only admin users can view pending approvals."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pending_approvals = TaskApproval.objects.filter(
            approver=request.user, action="pending"
        ).select_related("task", "task__client", "task__assigned_to")

        tasks = [approval.task for approval in pending_approvals]

        # Optimize queries for the TaskListSerializer
        task_ids = [task.id for task in tasks]
        optimized_tasks = (
            Task.objects.filter(id__in=task_ids)
            .select_related("assigned_to", "client")
            .prefetch_related(
                "approvals__approver",
                "approvals__next_approver",
                "status_history_records__changed_by",
            )
        )

        return Response(
            TaskListSerializer(optimized_tasks, many=True).data,
            status=status.HTTP_200_OK,
        )


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
