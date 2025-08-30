from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import permissions
from rest_framework.test import APIRequestFactory

from core.choices import TaskCategory, UserRoles
from core.models import Client, Task
from core.utils import get_today_local
from core.views import IsOwnerOrStaff

User = get_user_model()


class PermissionsTests(TestCase):
    """Test cases for custom permission classes"""

    def setUp(self):
        self.factory = APIRequestFactory()

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
        self.other_staff_user = User.objects.create_user(
            username="other_staff",
            email="other@example.com",
            role=UserRoles.STAFF,
        )

        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.staff_user,
        )
        self.task = Task.objects.create(
            client=self.client,
            assigned_to=self.staff_user,
            description="Test Task",
            deadline=get_today_local() + timedelta(days=7),
            category=TaskCategory.COMPLIANCE,
            period_covered="2025",
            engagement_date=get_today_local(),
        )

    def test_is_owner_or_staff_admin_has_permission(self):
        """Test that admin users have permission for any object"""
        permission = IsOwnerOrStaff()
        request = self.factory.get("/")
        request.user = self.admin_user

        # Should have permission for any object
        self.assertTrue(permission.has_object_permission(request, None, self.client))
        self.assertTrue(permission.has_object_permission(request, None, self.task))

    def test_is_owner_or_staff_owner_has_permission(self):
        """Test that object owners have permission"""
        permission = IsOwnerOrStaff()
        request = self.factory.get("/")
        request.user = self.staff_user

        # Staff user should have permission for their own client
        self.assertTrue(permission.has_object_permission(request, None, self.client))

        # Staff user should have permission for their own task
        self.assertTrue(permission.has_object_permission(request, None, self.task))

    def test_is_owner_or_staff_non_owner_no_permission(self):
        """Test that non-owners don't have permission"""
        permission = IsOwnerOrStaff()
        request = self.factory.get("/")
        request.user = self.other_staff_user

        # Other staff user should not have permission for different user's client
        self.assertFalse(permission.has_object_permission(request, None, self.client))

    def test_is_owner_or_staff_no_created_by_field(self):
        """Test permission for objects without created_by field"""
        permission = IsOwnerOrStaff()
        request = self.factory.get("/")
        request.user = self.staff_user

        # Create a task assigned to different user
        other_task = Task.objects.create(
            client=self.client,
            assigned_to=self.other_staff_user,
            description="Other Task",
            deadline=get_today_local() + timedelta(days=7),
            category=TaskCategory.COMPLIANCE,
            period_covered="2025",
            engagement_date=get_today_local(),
        )

        # Staff user should not have permission for task assigned to different user
        # (since Task doesn't have created_by field, it falls back to False)
        self.assertFalse(permission.has_object_permission(request, None, other_task))

    def test_is_owner_or_staff_unauthenticated_user(self):
        """Test permission for unauthenticated users"""
        permission = IsOwnerOrStaff()
        request = self.factory.get("/")
        request.user = None

        # Unauthenticated users should not have permission
        self.assertFalse(permission.has_object_permission(request, None, self.client))
        self.assertFalse(permission.has_object_permission(request, None, self.task))
