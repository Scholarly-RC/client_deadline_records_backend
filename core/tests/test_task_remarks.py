from django.contrib.auth import get_user_model
from django.test import TestCase

from core.actions import initiate_task_approval, process_task_approval
from core.choices import TaskCategory, TaskStatus, UserRoles
from core.models import Client, Task, TaskStatusHistory

User = get_user_model()


class TaskRemarksHandlingTests(TestCase):
    """Test cases for proper handling of task remarks vs system-generated messages"""

    def setUp(self):
        """Set up test data"""
        # Create test users
        self.staff_user = User.objects.create_user(
            username="staff",
            first_name="Staff",
            last_name="User",
            email="staff@example.com",
            role=UserRoles.STAFF,
        )

        self.admin1 = User.objects.create_user(
            username="admin1",
            first_name="Admin",
            last_name="One",
            email="admin1@example.com",
            role=UserRoles.ADMIN,
        )

        # Create test client
        self.test_client = Client.objects.create(
            name="Test Client", email="client@test.com", created_by=self.staff_user
        )

        # Create test task
        self.task = Task.objects.create(
            client=self.test_client,
            assigned_to=self.staff_user,
            category=TaskCategory.COMPLIANCE,
            description="Test Task for Remarks Handling",
            deadline="2025-12-31",
            status=TaskStatus.PENDING,
            period_covered="2025",
            engagement_date="2025-01-01",
            remarks="Original user remark",
        )

    def test_task_remarks_shows_latest_remark(self):
        """Test that task remarks always shows the latest remark from status history"""
        # Set initial user remark
        initial_user_remark = "Important user notes about this task"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=initial_user_remark,
            changed_by=self.staff_user,
            change_type="manual",
        )

        # Verify user remark is saved to task
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, initial_user_remark)

        # Initiate approval workflow (this generates system messages)
        initiate_task_approval(self.task, [self.admin1], self.staff_user)

        # Task remarks should now contain the approval workflow message (latest remark)
        self.task.refresh_from_db()
        self.assertIn("Approval workflow initiated", self.task.remarks)

        # Admin approves (this generates another system message)
        process_task_approval(
            self.task, self.admin1, "approved", "Admin approval comment"
        )

        # Task remarks should now contain the completion message (latest remark)
        self.task.refresh_from_db()
        self.assertIn("Approved and completed", self.task.remarks)
        self.assertIn("Admin approval comment", self.task.remarks)

    def test_latest_remark_always_updates_task_remarks(self):
        """Test that task.remarks is always updated with the latest remark"""
        original_remarks = self.task.remarks

        # Add system-generated status update
        system_message = "System generated approval message"
        self.task.add_status_update(
            new_status=TaskStatus.FOR_CHECKING,
            remarks=system_message,
            changed_by=self.admin1,
            change_type="approval",
        )

        # Task remarks should be updated with system message (latest remark)
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, system_message)

        # System message should also be in status history
        latest_history = TaskStatusHistory.objects.filter(task=self.task).first()
        self.assertEqual(latest_history.remarks, system_message)

    def test_user_remark_updates_task_remarks(self):
        """Test that user-provided remarks update the task.remarks field"""
        user_remark = "Updated user comment"

        # Add user remark
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=user_remark,
            changed_by=self.staff_user,
            change_type="manual",
        )

        # Task remarks should be updated
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, user_remark)

        # Status history should also contain the remark
        latest_history = TaskStatusHistory.objects.filter(task=self.task).first()
        self.assertEqual(latest_history.remarks, user_remark)

    def test_remarks_always_show_latest_regardless_of_type(self):
        """Test that task remarks always show the latest remark regardless of change_type"""
        # Manual change
        user_remark = "Manual user update"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=user_remark,
            changed_by=self.staff_user,
            change_type="manual",
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, user_remark)

        # Approval change should update task remarks (latest remark)
        system_message = "Approval system message"
        self.task.add_status_update(
            new_status=TaskStatus.FOR_CHECKING,
            remarks=system_message,
            changed_by=self.admin1,
            change_type="approval",
        )

        # Task remarks should now contain the system message (latest remark)
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, system_message)

        # Status history should contain both messages
        history_remarks = list(
            TaskStatusHistory.objects.filter(task=self.task)
            .order_by("-created_at")
            .values_list("remarks", flat=True)
        )

        self.assertIn(system_message, history_remarks)
        self.assertIn(user_remark, history_remarks)

    def test_latest_remark_property(self):
        """Test the latest_remark property returns the most recent remark"""
        # Add several status updates with different types
        user_remark_1 = "First user remark"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=user_remark_1,
            changed_by=self.staff_user,
            change_type="manual",
        )

        # Add system message
        system_message = "System generated message"
        self.task.add_status_update(
            new_status=TaskStatus.FOR_CHECKING,
            remarks=system_message,
            changed_by=self.admin1,
            change_type="approval",
        )

        # Add another user remark
        user_remark_2 = "Latest user remark"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=user_remark_2,
            changed_by=self.staff_user,
            change_type="manual",
        )

        # latest_remark should return the most recent remark (regardless of type)
        self.assertEqual(self.task.latest_remark, user_remark_2)

    def test_force_history_with_remarks_handling(self):
        """Test force_history parameter works correctly with remarks handling"""
        original_remarks = self.task.remarks

        # Use force_history with system message
        system_message = "Forced system message"
        self.task.add_status_update(
            new_status=TaskStatus.PENDING,  # Same status
            remarks=system_message,
            changed_by=self.admin1,
            change_type="approval",
            force_history=True,
        )

        # Task remarks should be updated to the new message
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, system_message)

        # Status history should be created
        forced_history = TaskStatusHistory.objects.filter(
            task=self.task, remarks=system_message
        ).first()
        self.assertIsNotNone(forced_history)
        self.assertEqual(forced_history.old_status, TaskStatus.PENDING)
        self.assertEqual(forced_history.new_status, TaskStatus.PENDING)

    def test_complete_approval_workflow_latest_remarks(self):
        """Test that task remarks shows the latest remark throughout approval workflow"""
        # Set initial user remark
        user_remark = "Important task notes that should be preserved"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks=user_remark,
            changed_by=self.staff_user,
            change_type="manual",
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, user_remark)

        # Go through complete approval workflow
        initiate_task_approval(self.task, [self.admin1], self.staff_user)

        # Task remarks should now show the workflow initiation message
        self.task.refresh_from_db()
        self.assertIn("Approval workflow initiated", self.task.remarks)

        process_task_approval(self.task, self.admin1, "approved", "Admin approval")

        # Task remarks should now show the completion message (latest)
        self.task.refresh_from_db()
        self.assertIn("Approved and completed", self.task.remarks)
        self.assertIn("Admin approval", self.task.remarks)

        # Status history should contain all the messages
        approval_messages = TaskStatusHistory.objects.filter(
            task=self.task, change_type="approval"
        ).order_by("-created_at")

        self.assertGreater(approval_messages.count(), 0)

        # Latest message should match task remarks
        latest_approval_message = approval_messages.first().remarks
        self.assertEqual(self.task.remarks, latest_approval_message)
