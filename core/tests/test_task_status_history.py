from django.contrib.auth import get_user_model
from django.test import TestCase

from core.choices import TaskCategory, TaskStatus
from core.models import Client, Task, TaskStatusHistory

User = get_user_model()


class TaskStatusHistoryTests(TestCase):
    """Test cases for Task status history functionality"""

    def setUp(self):
        """Set up test data"""
        self.test_user = User.objects.create_user(
            username="testuser",
            first_name="Test",
            last_name="User",
            email="test@example.com",
        )

        self.test_client = Client.objects.create(
            name="Test Client", email="client@test.com", created_by=self.test_user
        )

        self.task = Task.objects.create(
            client=self.test_client,
            assigned_to=self.test_user,
            category=TaskCategory.COMPLIANCE,
            description="Test Task for Status History",
            deadline="2025-12-31",
            status=TaskStatus.PENDING,
            period_covered="2025",
            engagement_date="2025-01-01",
        )

    def test_add_status_update_no_change(self):
        """Test that no status history entry is created when status doesn't change"""
        initial_count = TaskStatusHistory.objects.filter(task=self.task).count()

        # Update to same status
        self.task.add_status_update(
            new_status=TaskStatus.PENDING,
            remarks="No change test",
            changed_by=self.test_user,
        )

        final_count = TaskStatusHistory.objects.filter(task=self.task).count()
        self.assertEqual(
            initial_count,
            final_count,
            "Status history should not be created for same status",
        )

        # Verify task status remains the same
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.PENDING)

    def test_add_status_update_with_change(self):
        """Test that status history entry is created when status changes"""
        initial_count = TaskStatusHistory.objects.filter(task=self.task).count()

        # Update to different status
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks="Status change test",
            changed_by=self.test_user,
        )

        final_count = TaskStatusHistory.objects.filter(task=self.task).count()
        self.assertEqual(
            initial_count + 1,
            final_count,
            "Status history should be created for status change",
        )

        # Verify task status changed
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.ON_GOING)

        # Verify status history content
        history_entry = TaskStatusHistory.objects.filter(task=self.task).first()
        self.assertEqual(history_entry.old_status, TaskStatus.PENDING)
        self.assertEqual(history_entry.new_status, TaskStatus.ON_GOING)
        self.assertEqual(history_entry.changed_by, self.test_user)
        self.assertEqual(history_entry.remarks, "Status change test")

    def test_add_status_update_remarks_only(self):
        """Test updating remarks without changing status"""
        initial_count = TaskStatusHistory.objects.filter(task=self.task).count()
        original_remarks = self.task.remarks

        # Update with remarks but same status
        self.task.add_status_update(
            new_status=TaskStatus.PENDING,
            remarks="Updated remarks only",
            changed_by=self.test_user,
        )

        # No status history should be created
        final_count = TaskStatusHistory.objects.filter(task=self.task).count()
        self.assertEqual(initial_count, final_count)

        # Verify remarks were updated
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, "Updated remarks only")

    def test_multiple_status_changes(self):
        """Test multiple status changes create correct history"""
        # First change
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks="First change",
            changed_by=self.test_user,
        )

        # Second change
        self.task.add_status_update(
            new_status=TaskStatus.FOR_CHECKING,
            remarks="Second change",
            changed_by=self.test_user,
        )

        # Should have 2 status history entries
        history_count = TaskStatusHistory.objects.filter(task=self.task).count()
        self.assertEqual(history_count, 2)

        # Verify current status
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.FOR_CHECKING)

        # Verify history order (most recent first)
        history_entries = list(
            TaskStatusHistory.objects.filter(task=self.task).order_by("-created_at")
        )

        # Most recent entry
        self.assertEqual(history_entries[0].old_status, TaskStatus.ON_GOING)
        self.assertEqual(history_entries[0].new_status, TaskStatus.FOR_CHECKING)
        self.assertEqual(history_entries[0].remarks, "Second change")

        # First entry
        self.assertEqual(history_entries[1].old_status, TaskStatus.PENDING)
        self.assertEqual(history_entries[1].new_status, TaskStatus.ON_GOING)
        self.assertEqual(history_entries[1].remarks, "First change")
