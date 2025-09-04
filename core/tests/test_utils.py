from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.choices import TaskCategory, UserRoles
from core.models import Client, Task
from core.utils import (get_admin_users, get_notification_recipients,
                        get_now_local, get_today_local)

User = get_user_model()


class UtilsTests(TestCase):
    """Test cases for utility functions"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            role=UserRoles.ADMIN,
        )
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            role=UserRoles.STAFF,
        )
        self.superuser = User.objects.create_superuser(
            username="superuser",
            email="super@example.com",
            password="testpass123",
        )
        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.admin_user,
        )

    def test_get_admin_users(self):
        """Test get_admin_users returns only admin users"""
        admin_users = get_admin_users()

        # Should include admin user but not staff or superuser
        self.assertIn(self.admin_user, admin_users)
        self.assertNotIn(self.staff_user, admin_users)
        self.assertNotIn(self.superuser, admin_users)

        # Should be a queryset
        self.assertEqual(len(admin_users), 1)
        self.assertEqual(admin_users[0], self.admin_user)

    def test_get_notification_recipients_with_assigned_user(self):
        """Test get_notification_recipients with assigned user"""
        task = Task.objects.create(
            client=self.client,
            assigned_to=self.staff_user,
            description="Test Task",
            deadline=get_today_local() + timedelta(days=7),
            category=TaskCategory.COMPLIANCE,
            period_covered="2025",
            engagement_date=get_today_local(),
        )

        recipients = get_notification_recipients(task)

        # Should include both admin and assigned user
        self.assertIn(self.admin_user, recipients)
        self.assertIn(self.staff_user, recipients)
        self.assertEqual(len(recipients), 2)

    @patch("core.utils.timezone")
    def test_get_now_local(self, mock_timezone):
        """Test get_now_local returns local time"""
        from datetime import datetime

        mock_now = datetime(2025, 1, 15, 10, 30, 45)
        mock_timezone.localtime.return_value = mock_now
        mock_timezone.now.return_value = mock_now

        result = get_now_local()

        self.assertEqual(result, mock_now)
        mock_timezone.localtime.assert_called_once_with(mock_now)

    @patch("core.utils.timezone")
    def test_get_today_local(self, mock_timezone):
        """Test get_today_local returns local date"""
        from datetime import date
        from unittest.mock import MagicMock

        mock_now = MagicMock()
        mock_today = date(2025, 1, 15)
        mock_now.date.return_value = mock_today
        mock_timezone.localtime.return_value = mock_now

        result = get_today_local()

        self.assertEqual(result, mock_today)
        mock_timezone.localtime.assert_called_once_with(mock_timezone.now.return_value)

    def test_get_today_local_integration(self):
        """Test get_today_local returns actual date"""
        result = get_today_local()

        # Should return a date object
        self.assertIsInstance(result, type(get_today_local()))

        # Should be today's date
        from datetime import date

        today = date.today()
        self.assertEqual(result, today)
