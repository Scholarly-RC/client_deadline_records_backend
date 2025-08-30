from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.choices import (
    ClientStatus,
    TaskCategory,
    TaskStatus,
    TaxCaseCategory,
    TypeOfTaxCase,
    UserRoles,
)
from core.models import Client, Task, TaskApproval
from core.utils import get_now_local, get_today_local

User = get_user_model()


class StatisticsEndpointTests(TestCase):
    """Comprehensive test cases for the enhanced statistics endpoint"""

    STATISTICS_URL = "/api/tasks/statistics/"

    def setUp(self):
        """Set up test data following project specification memory guidelines"""
        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin_test",
            first_name="Admin",
            last_name="User",
            email="admin@test.com",
            role=UserRoles.ADMIN,
        )

        self.staff_user = User.objects.create_user(
            username="staff_test",
            first_name="Staff",
            last_name="User",
            email="staff@test.com",
            role=UserRoles.STAFF,
        )

        # Create test clients
        self.active_client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            status=ClientStatus.ACTIVE,
            created_by=self.admin_user,
        )

        # Setup API client
        self.api_client = APIClient()
        self.now = get_now_local()
        self.today = self.now.date()

        # Create test tasks
        self._create_test_tasks()

    def _create_test_tasks(self):
        """Create test task data"""
        # Completed task
        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Completed Task",
            deadline=self.today + timedelta(days=5),
            completion_date=self.today - timedelta(days=1),
            status=TaskStatus.COMPLETED,
            priority="high",
            period_covered="2025",
            engagement_date=self.today - timedelta(days=10),
            last_update=self.now - timedelta(days=1),
        )

        # Overdue task
        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.TAX_CASE,
            description="Overdue Tax Case",
            deadline=self.today - timedelta(days=10),
            status=TaskStatus.ON_GOING,
            priority="high",
            tax_category=TaxCaseCategory.ONE_TIME_ENGAGEMENT,
            tax_type=TypeOfTaxCase.INCOME_TAX,
            tax_payable=Decimal("50000.00"),
            period_covered="2024",
            engagement_date=self.today - timedelta(days=20),
            working_paper="WP-2024-001",
            last_update=self.today - timedelta(days=3),
        )

        # Task with approval workflow
        approval_task = Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Task For Checking",
            deadline=self.today + timedelta(days=15),
            status=TaskStatus.FOR_CHECKING,
            priority="medium",
            requires_approval=True,
            current_approval_step=1,
            period_covered="2025",
            engagement_date=self.today - timedelta(days=5),
            last_update=self.now - timedelta(days=1),
        )

        # Create approval record
        TaskApproval.objects.create(
            task=approval_task,
            approver=self.admin_user,
            action="pending",
            step_number=1,
        )

    def _authenticate_user(self, user):
        """Helper method to authenticate user for API requests"""
        refresh = RefreshToken.for_user(user)
        token = str(refresh.access_token)
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_authentication_required(self):
        """Test that authentication is required"""
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_data_structure_completeness(self):
        """Test all required data structure sections are present"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Test main sections per specification memory
        required_sections = [
            "summary",
            "charts_data",
            "performance_metrics",
            "team_analytics",
            "client_insights",
            "business_intelligence",
            "quick_actions",
            "metadata",
        ]

        for section in required_sections:
            self.assertIn(section, data, f"Missing required section: {section}")

    def test_summary_statistics_accuracy(self):
        """Test accuracy of summary statistics calculations"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)

        data = response.data
        summary = data["summary"]

        # Test basic counts
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["for_checking"], 1)

        # Test priority distribution
        self.assertEqual(summary["high_priority"], 2)
        self.assertEqual(summary["medium_priority"], 1)

        # Test overdue tasks
        self.assertEqual(summary["overdue"], 1)

    def test_role_based_data_filtering(self):
        """Test data filtering based on user role"""
        # Test admin sees all data
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)

        admin_data = response.data
        self.assertEqual(admin_data["summary"]["total"], 3)
        self.assertEqual(admin_data["metadata"]["data_scope"], "all_tasks")

        # Test staff sees only assigned tasks
        self._authenticate_user(self.staff_user)
        response = self.api_client.get(url)

        staff_data = response.data
        staff_task_count = Task.objects.filter(assigned_to=self.staff_user).count()
        self.assertEqual(staff_data["summary"]["total"], staff_task_count)
        self.assertEqual(staff_data["metadata"]["data_scope"], "assigned_tasks")

    def test_date_range_filtering(self):
        """Test filtering statistics by date range"""
        self._authenticate_user(self.admin_user)

        # Create additional test tasks for different dates
        # Task from last week
        last_week_date = self.now.date() - timedelta(days=7)

        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Last Week Task",
            deadline=last_week_date + timedelta(days=5),
            completion_date=last_week_date - timedelta(days=1),
            status=TaskStatus.COMPLETED,
            priority="medium",
            period_covered=str(last_week_date.year),
            engagement_date=last_week_date - timedelta(days=10),
            last_update=last_week_date - timedelta(days=1),
        )

        # Test filtering by date range (last 3 days)
        start_date = (self.today - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = self.now.date().strftime("%Y-%m-%d")
        url = f"{self.STATISTICS_URL}?start_date={start_date}&end_date={end_date}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include tasks from the last 3 days
        self.assertEqual(data["summary"]["total"], 3)  # Original 3 tasks

        # Test filtering by date range (last week)
        start_date = (self.today - timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = (self.today - timedelta(days=5)).strftime("%Y-%m-%d")
        url = f"{self.STATISTICS_URL}?start_date={start_date}&end_date={end_date}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include only the last week task
        self.assertEqual(data["summary"]["total"], 1)
        self.assertEqual(data["summary"]["completed"], 1)

    def test_start_date_only_filtering(self):
        """Test filtering statistics by start_date only"""
        self._authenticate_user(self.admin_user)

        # Create task from last week
        last_week_date = self.now.date() - timedelta(days=7)

        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Last Week Task",
            deadline=last_week_date + timedelta(days=5),
            completion_date=last_week_date - timedelta(days=1),
            status=TaskStatus.COMPLETED,
            priority="low",
            period_covered=str(last_week_date.year),
            engagement_date=last_week_date - timedelta(days=10),
            last_update=last_week_date - timedelta(days=1),
        )

        # Test filtering by start_date only (from 2 days ago)
        start_date = (self.today - timedelta(days=2)).strftime("%Y-%m-%d")
        url = f"{self.STATISTICS_URL}?start_date={start_date}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include tasks from the last 2 days (2 tasks: yesterday and yesterday, excluding the one from 3 days ago)
        self.assertEqual(data["summary"]["total"], 2)

        # Test filtering by start_date only (from 10 days ago)
        start_date = (self.today - timedelta(days=10)).strftime("%Y-%m-%d")
        url = f"{self.STATISTICS_URL}?start_date={start_date}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include tasks from the last 10 days (original 3 + last week task)
        self.assertEqual(data["summary"]["total"], 4)

    def test_end_date_only_filtering(self):
        """Test filtering statistics by end_date only"""
        self._authenticate_user(self.admin_user)

        # Create task from last week
        last_week_date = self.now.date() - timedelta(days=7)

        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Last Week Task",
            deadline=last_week_date + timedelta(days=5),
            completion_date=last_week_date - timedelta(days=1),
            status=TaskStatus.COMPLETED,
            priority="low",
            period_covered=str(last_week_date.year),
            engagement_date=last_week_date - timedelta(days=10),
            last_update=last_week_date - timedelta(days=1),
        )

        # Test filtering by end_date only (up to today)
        end_date = self.now.date().strftime("%Y-%m-%d")
        url = f"{self.STATISTICS_URL}?end_date={end_date}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include all tasks up to today (original 3 + last week task)
        self.assertEqual(data["summary"]["total"], 4)

    def test_invalid_date_parameters(self):
        """Test handling of invalid date parameters"""
        self._authenticate_user(self.admin_user)

        # Test invalid date format
        url = f"{self.STATISTICS_URL}?start_date=invalid-date&end_date={self.today.strftime('%Y-%m-%d')}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Test invalid end_date format
        url = f"{self.STATISTICS_URL}?start_date={self.today.strftime('%Y-%m-%d')}&end_date=invalid-date"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Test start_date after end_date
        yesterday = self.now.date() - timedelta(days=1)
        url = f"{self.STATISTICS_URL}?start_date={self.today.strftime('%Y-%m-%d')}&end_date={yesterday.strftime('%Y-%m-%d')}"
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_no_filtering_parameters(self):
        """Test that endpoint works without filtering parameters (current behavior)"""
        self._authenticate_user(self.admin_user)

        url = self.STATISTICS_URL
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Should include all tasks
        self.assertEqual(data["summary"]["total"], 3)

        # Check metadata includes filter info
        self.assertIn("filters_applied", data["metadata"])
        self.assertEqual(data["metadata"]["filters_applied"], {})
