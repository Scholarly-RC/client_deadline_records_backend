"""
Unit tests for the task assignment notification functionality in views.py
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from core.actions import create_notifications
from core.models import Client, Task
from core.views import TaskViewSet


class TaskNotificationTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.admin_user = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        self.regular_user = get_user_model().objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass123",
            first_name="Regular",
            last_name="User",
        )

        # Create test client
        self.client_obj = Client.objects.create(
            name="Test Client",
            contact_person="Test Contact",
            email="client@example.com",
        )

        # Create API client and authenticate as admin
        self.api_client = APIClient()
        refresh = RefreshToken.for_user(self.admin_user)
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Create request factory
        self.factory = APIRequestFactory()

    @patch("core.views.create_notifications")
    def test_task_creation_notification(self, mock_create_notifications):
        """Test that notification is sent when task is created and assigned"""
        # Create a task via API
        response = self.api_client.post(
            "/api/tasks/",
            {
                "client": self.client_obj.id,
                "category": "compliance",
                "description": "Test task notification",
                "assigned_to": self.regular_user.id,
                "priority": "medium",
                "deadline": "2025-12-31",
                "status": "not_yet_started",
                "period_covered": "2025",
                "engagement_date": "2025-01-01",
            },
            format="json",
        )

        # Check that the task was created successfully
        self.assertEqual(response.status_code, 201)

        # Check that create_notifications was called once
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="New Task Assigned",
            message="A new task 'Test task notification' has been assigned to you.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_creation_no_notification_for_self_assignment(
        self, mock_create_notifications
    ):
        """Test that no notification is sent when admin assigns task to themselves"""
        # Create a task assigned to the admin user
        response = self.api_client.post(
            "/api/tasks/",
            {
                "client": self.client_obj.id,
                "category": "compliance",
                "description": "Test self-assigned task",
                "assigned_to": self.admin_user.id,
                "priority": "medium",
                "deadline": "2025-12-31",
                "status": "not_yet_started",
                "period_covered": "2025",
                "engagement_date": "2025-01-01",
            },
            format="json",
        )

        # Check that the task was created successfully
        self.assertEqual(response.status_code, 201)

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()

    @patch("core.views.create_notifications")
    def test_task_creation_with_missing_required_fields(
        self, mock_create_notifications
    ):
        """Test that task creation fails with missing required fields"""
        # Create a task without required fields
        response = self.api_client.post(
            "/api/tasks/",
            {
                "client": self.client_obj.id,
                "category": "compliance",
                "description": "Test incomplete task",
                # Missing assigned_to, priority, deadline, period_covered, engagement_date
            },
            format="json",
        )

        # Check that the task creation failed
        self.assertEqual(response.status_code, 400)

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()

    @patch("core.views.create_notifications")
    def test_task_update_notification_on_reassignment(self, mock_create_notifications):
        """Test that notification is sent when task is reassigned"""
        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for reassignment",
            assigned_to=self.admin_user,  # Initially assigned to admin
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update the task to reassign it
        response = self.api_client.patch(
            f"/api/tasks/{task.id}/",
            {"assigned_to": self.regular_user.id},
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was called once (only for new assignee since admin is doing the reassignment)
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="Task Reassigned",
            message="The task 'Test task for reassignment' has been reassigned to you.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_update_notification_when_not_reassigned(
        self, mock_create_notifications
    ):
        """Test that notification is sent to assigned user when task is updated but not reassigned"""
        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for update",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update the task without changing assignment
        response = self.api_client.patch(
            f"/api/tasks/{task.id}/",
            {"description": "Updated task description"},
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was called for the assigned user
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="Task Updated",
            message="The task 'Updated task description' has been updated.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_update_notification_to_assigned_user(self, mock_create_notifications):
        """Test that notification is sent to assigned user when task is updated"""
        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for update notification",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update the task (change description)
        response = self.api_client.patch(
            f"/api/tasks/{task.id}/",
            {"description": "Updated task description"},
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was called for the assigned user
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="Task Updated",
            message="The task 'Updated task description' has been updated.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_update_no_notification_when_updater_is_assigned_user(self, mock_create_notifications):
        """Test that no notification is sent when the assigned user updates their own task"""
        # Create API client and authenticate as regular user
        regular_api_client = APIClient()
        refresh = RefreshToken.for_user(self.regular_user)
        regular_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Create a task assigned to the regular user
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for self-update",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update the task as the assigned user
        response = regular_api_client.patch(
            f"/api/tasks/{task.id}/",
            {"description": "Self-updated task description"},
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()

    @patch("core.views.create_notifications")
    def test_task_update_notification_on_multiple_fields_change(self, mock_create_notifications):
        """Test that notification is sent when multiple fields are updated"""
        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for multiple updates",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update multiple fields
        response = self.api_client.patch(
            f"/api/tasks/{task.id}/",
            {
                "description": "Updated description",
                "priority": "high",
                "remarks": "Updated remarks"
            },
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was called once
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="Task Updated",
            message="The task 'Updated description' has been updated.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_update_notifications_on_reassignment_and_update(self, mock_create_notifications):
        """Test that both new and previous assignees are notified when task is reassigned with updates"""
        # Create another user for reassignment
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="otherpass123",
            first_name="Other",
            last_name="User",
        )

        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for reassignment and update",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Update both assigned_to and other fields
        response = self.api_client.patch(
            f"/api/tasks/{task.id}/",
            {
                "assigned_to": other_user.id,
                "description": "Updated description",
                "priority": "high"
            },
            format="json",
        )

        # Check that the task was updated successfully
        self.assertEqual(response.status_code, 200)

        # Check that create_notifications was called twice (for both assignees)
        self.assertEqual(mock_create_notifications.call_count, 2)

        # Check the calls were made with correct parameters
        mock_create_notifications.assert_any_call(
            recipient=other_user,
            title="Task Reassigned",
            message="The task 'Updated description' has been reassigned to you.",
            link="/my-deadlines",
        )

        mock_create_notifications.assert_any_call(
            recipient=self.regular_user,
            title="Task Reassigned",
            message=f"The task 'Updated description' has been reassigned to {other_user.fullname}.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_deletion_notification_to_assigned_user(self, mock_create_notifications):
        """Test that notification is sent to assigned user when task is deleted"""
        # Create a task first
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for deletion notification",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Delete the task
        response = self.api_client.delete(f"/api/tasks/{task.id}/")

        # Check that the task was deleted successfully
        self.assertEqual(response.status_code, 204)

        # Check that create_notifications was called for the assigned user
        mock_create_notifications.assert_called_once_with(
            recipient=self.regular_user,
            title="Task Deleted",
            message="The task 'Test task for deletion notification' has been deleted.",
            link="/my-deadlines",
        )

    @patch("core.views.create_notifications")
    def test_task_deletion_no_notification_when_deleter_is_assigned_user(self, mock_create_notifications):
        """Test that no notification is sent when assigned user deletes their own task"""
        # Create API client and authenticate as regular user
        regular_api_client = APIClient()
        refresh = RefreshToken.for_user(self.regular_user)
        regular_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Create a task assigned to the regular user
        task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Test task for self-deletion",
            assigned_to=self.regular_user,
            priority="medium",
            deadline="2025-12-31",
            status="not_yet_started",
            period_covered="2025",
            engagement_date="2025-01-01",
        )

        # Delete the task as the assigned user
        response = regular_api_client.delete(f"/api/tasks/{task.id}/")

        # Check that the task was deleted successfully
        self.assertEqual(response.status_code, 204)

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()


