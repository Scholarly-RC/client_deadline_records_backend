from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.actions import create_log
from core.models import AppLog, Client, Task

User = get_user_model()


class AppLogTests(TestCase):
    """Test cases for AppLog functionality"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            first_name="Admin",
            last_name="User",
            email="admin@test.com",
            role="admin",
        )
        self.staff_user = User.objects.create_user(
            username="staff",
            first_name="Staff",
            last_name="User",
            email="staff@test.com",
            role="staff",
        )
        self.test_client = Client.objects.create(
            name="Test Client", email="client@test.com", created_by=self.admin_user
        )

        # Set up API client for testing viewsets
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

    def test_create_log_function(self):
        """Test the create_log function creates log entries correctly"""
        initial_count = AppLog.objects.count()

        # Create a log entry
        create_log(self.admin_user, "Test log message")

        # Check that log was created
        self.assertEqual(AppLog.objects.count(), initial_count + 1)

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertEqual(log_entry.details, "Test log message")

    def test_task_status_change_logging(self):
        """Test that task status changes are logged"""
        task = Task.objects.create(
            client=self.test_client,
            assigned_to=self.staff_user,
            category="compliance",
            description="Test Task for Logging",
            deadline="2025-12-31",
            status="pending",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        initial_log_count = AppLog.objects.count()

        # Change task status from PENDING to ON_GOING
        task.add_status_update(
            new_status="on_going",
            remarks="Starting work on task",
            changed_by=self.admin_user,
        )

        # Check that log was created
        self.assertEqual(AppLog.objects.count(), initial_log_count + 1)

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertIn("Task status changed", log_entry.details)
        # Just verify that the log contains status change information
        self.assertIn("from", log_entry.details)
        self.assertIn("to", log_entry.details)

    def test_task_creation_logging(self):
        """Test that task creation is logged"""
        initial_log_count = AppLog.objects.count()

        # Create task via API to trigger viewset logging
        task_data = {
            "client": self.test_client.id,
            "assigned_to": self.staff_user.id,
            "category": "compliance",
            "description": "Test Task Creation",
            "deadline": "2025-12-31",
            "status": "pending",
            "period_covered": "2025",
            "engagement_date": "2025-01-01",
            "priority": "medium",  # Add required priority field
        }

        response = self.client.post("/api/tasks/", task_data, format="json")
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response data: {response.data}")  # Debug info
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that log was created during task creation
        self.assertEqual(AppLog.objects.count(), initial_log_count + 1)

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertIn("Created task", log_entry.details)

    def test_client_creation_logging(self):
        """Test that client creation is logged"""
        initial_log_count = AppLog.objects.count()

        # Create client via API to trigger viewset logging
        client_data = {
            "name": "New Test Client",
            "email": "newclient@test.com",
        }

        response = self.client.post("/api/clients/", client_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that log was created during client creation
        self.assertEqual(AppLog.objects.count(), initial_log_count + 1)

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertIn("Created client", log_entry.details)

    def test_document_upload_logging(self):
        """Test that document upload is logged"""
        initial_log_count = AppLog.objects.count()

        # Create document via API to trigger viewset logging
        test_file = BytesIO(b"Test content")
        test_file.name = "test.pdf"

        document_data = {
            "client": self.test_client.id,
            "title": "Test Document",
            "document_file": test_file,
        }

        response = self.client.post(
            "/api/client-documents/", document_data, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that log was created during document upload
        self.assertEqual(AppLog.objects.count(), initial_log_count + 1)

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertIn("Uploaded document", log_entry.details)

    def test_approval_workflow_logging(self):
        """Test that approval workflow actions are logged"""
        from core.actions import initiate_task_approval, process_task_approval

        task = Task.objects.create(
            client=self.test_client,
            assigned_to=self.staff_user,
            category="compliance",
            description="Test Approval Task",
            deadline="2025-12-31",
            status="pending",
            period_covered="2025",
            engagement_date="2025-01-01",
            requires_approval=True,
        )

        initial_log_count = AppLog.objects.count()

        # Initiate approval workflow
        initiate_task_approval(task, [self.admin_user], self.staff_user)

        # Check that log was created
        self.assertGreater(AppLog.objects.count(), initial_log_count)

        # Process approval
        process_task_approval(task, self.admin_user, "approved", "Looks good", None)

        # Check that more logs were created
        self.assertGreater(AppLog.objects.count(), initial_log_count + 1)

    def test_log_entries_are_properly_ordered(self):
        """Test that log entries are ordered by creation time"""
        # Create multiple log entries
        create_log(self.admin_user, "First log")
        create_log(self.admin_user, "Second log")
        create_log(self.admin_user, "Third log")

        # Get all logs for this user
        logs = AppLog.objects.filter(user=self.admin_user).order_by("-created_at")

        # Check ordering
        self.assertEqual(logs[0].details, "Third log")
        self.assertEqual(logs[1].details, "Second log")
        self.assertEqual(logs[2].details, "First log")

    def test_log_entries_contain_user_info(self):
        """Test that log entries properly reference users"""
        create_log(self.admin_user, "Admin action log")

        log_entry = AppLog.objects.latest("created_at")
        self.assertEqual(log_entry.user, self.admin_user)
        self.assertEqual(
            str(log_entry),
            f"{self.admin_user.fullname} - Admin action log - {log_entry.created_at.date()}",
        )
