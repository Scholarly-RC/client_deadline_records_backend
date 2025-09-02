"""
Unit tests for the notification functions in core/actions.py
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.actions import (
    send_notification_for_due_tasks,
    send_notification_on_reminder_date,
)
from core.models import Client, Task, User
from core.utils import get_today_local


class NotificationTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.user1 = User.objects.create_user(
            username="testuser1",
            email="test1@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User1",
        )

        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User2",
        )

        # Create test client
        self.client_obj = Client.objects.create(
            name="Test Client",
            contact_person="Test Contact",
            email="client@example.com",
        )

        # Create tasks with different deadlines
        self.today = get_today_local()
        self.reminder_date = self.today + timedelta(days=3)

        # Task due today
        self.due_today_task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Task due today",
            assigned_to=self.user1,
            priority="medium",
            deadline=self.today,
            status="pending",
        )

        # Task with reminder date (due in 3 days)
        self.reminder_task = Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Task with reminder",
            assigned_to=self.user2,
            priority="medium",
            deadline=self.reminder_date,
            status="pending",
        )

    @patch("core.actions.create_notifications")
    def test_send_notification_for_due_tasks(self, mock_create_notifications):
        """Test that notifications are sent for tasks due today"""
        send_notification_for_due_tasks()

        # Check that create_notifications was called for the task due today
        mock_create_notifications.assert_called_once_with(
            recipient=self.user1,
            title="Action Required: Task Due Today",
            message=f"Urgent: The task 'Task due today' is due today. Please complete and submit as soon as possible.",
            link="/my-deadlines",
        )

    @patch("core.actions.create_notifications")
    def test_send_notification_on_reminder_date(self, mock_create_notifications):
        """Test that notifications are sent for tasks with upcoming deadlines"""
        send_notification_on_reminder_date()

        # Check that create_notifications was called for the task with reminder
        mock_create_notifications.assert_called_once_with(
            recipient=self.user2,
            title="Upcoming Task Reminder",
            message=f"Friendly reminder: The task 'Task with reminder' is due on {self.reminder_date.strftime('%b %d, %Y')}. Please review your task.",
            link="/my-deadlines",
        )

    @patch("core.actions.create_notifications")
    def test_send_notification_for_due_tasks_no_tasks(self, mock_create_notifications):
        """Test that no notifications are sent when there are no tasks due today"""
        # Delete all tasks
        Task.objects.all().delete()

        send_notification_for_due_tasks()

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()

    @patch("core.actions.create_notifications")
    def test_send_notification_on_reminder_date_no_tasks(
        self, mock_create_notifications
    ):
        """Test that no notifications are sent when there are no tasks with upcoming deadlines"""
        # Delete all tasks
        Task.objects.all().delete()

        send_notification_on_reminder_date()

        # Check that create_notifications was not called
        mock_create_notifications.assert_not_called()

    @patch("core.actions.create_notifications")
    def test_send_notification_for_multiple_due_tasks(self, mock_create_notifications):
        """Test that notifications are sent for multiple tasks due today"""
        # Create another task due today
        Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Another task due today",
            assigned_to=self.user2,
            priority="medium",
            deadline=self.today,
            status="pending",
        )

        send_notification_for_due_tasks()

        # Check that create_notifications was called twice
        self.assertEqual(mock_create_notifications.call_count, 2)

        # Check the calls were made with correct parameters
        mock_create_notifications.assert_any_call(
            recipient=self.user1,
            title="Action Required: Task Due Today",
            message=f"Urgent: The task 'Task due today' is due today. Please complete and submit as soon as possible.",
            link="/my-deadlines",
        )

        mock_create_notifications.assert_any_call(
            recipient=self.user2,
            title="Action Required: Task Due Today",
            message=f"Urgent: The task 'Another task due today' is due today. Please complete and submit as soon as possible.",
            link="/my-deadlines",
        )

    @patch("core.actions.create_notifications")
    def test_send_notification_on_reminder_date_multiple_tasks(
        self, mock_create_notifications
    ):
        """Test that notifications are sent for multiple tasks with upcoming deadlines"""
        # Create another task with reminder date
        Task.objects.create(
            client=self.client_obj,
            category="compliance",
            description="Another task with reminder",
            assigned_to=self.user1,
            priority="medium",
            deadline=self.reminder_date,
            status="pending",
        )

        send_notification_on_reminder_date()

        # Check that create_notifications was called twice
        self.assertEqual(mock_create_notifications.call_count, 2)

        # Check the calls were made with correct parameters
        mock_create_notifications.assert_any_call(
            recipient=self.user1,
            title="Upcoming Task Reminder",
            message=f"Friendly reminder: The task 'Another task with reminder' is due on {self.reminder_date.strftime('%b %d, %Y')}. Please review your task.",
            link="/my-deadlines",
        )

        mock_create_notifications.assert_any_call(
            recipient=self.user2,
            title="Upcoming Task Reminder",
            message=f"Friendly reminder: The task 'Task with reminder' is due on {self.reminder_date.strftime('%b %d, %Y')}. Please review your task.",
            link="/my-deadlines",
        )
