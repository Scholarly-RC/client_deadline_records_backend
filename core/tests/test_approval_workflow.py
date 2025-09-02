from django.contrib.auth import get_user_model
from django.test import TestCase

from core.actions import initiate_task_approval, process_task_approval
from core.choices import TaskCategory, TaskStatus, UserRoles
from core.models import Client, Task, TaskApproval, TaskStatusHistory

User = get_user_model()


class ApprovalWorkflowTests(TestCase):
    """Test cases for approval workflow functionality"""

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

        self.admin2 = User.objects.create_user(
            username="admin2",
            first_name="Admin",
            last_name="Two",
            email="admin2@example.com",
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
            description="Test Task for Approval Workflow",
            deadline="2025-12-31",
            status=TaskStatus.PENDING,
            period_covered="2025",
            engagement_date="2025-01-01",
        )

    def test_approval_workflow_reinitialization_after_rejection(self):
        """Test that approval workflow can be re-initialized after rejection without UNIQUE constraint error"""
        # Initial approval setup
        approvers = [self.admin1]
        initiate_task_approval(self.task, approvers, self.staff_user)

        # Verify initial state
        self.assertTrue(self.task.requires_approval)
        self.assertEqual(self.task.current_approval_step, 1)
        self.assertEqual(TaskApproval.objects.filter(task=self.task).count(), 1)

        # Admin1 rejects the task
        process_task_approval(self.task, self.admin1, "rejected", "Needs more work")

        # Verify rejection state
        self.task.refresh_from_db()
        self.assertFalse(self.task.requires_approval)
        self.assertEqual(self.task.current_approval_step, 0)
        self.assertEqual(self.task.status, TaskStatus.FOR_REVISION)

        # Try to re-initialize with same admin - this should NOT fail with UNIQUE constraint error
        try:
            initiate_task_approval(self.task, approvers, self.staff_user)
            reinitialization_successful = True
        except Exception as e:
            reinitialization_successful = False
            self.fail(f"Re-initialization failed with error: {str(e)}")

        self.assertTrue(reinitialization_successful, "Re-initialization should succeed")

        # Verify re-initialized state
        self.task.refresh_from_db()
        self.assertTrue(self.task.requires_approval)
        self.assertEqual(self.task.current_approval_step, 1)
        self.assertEqual(self.task.status, TaskStatus.FOR_CHECKING)

        # Should have fresh approval records
        approval_records = TaskApproval.objects.filter(task=self.task, action="pending")
        self.assertEqual(approval_records.count(), 1)
        self.assertEqual(approval_records.first().approver, self.admin1)

    def test_approval_workflow_reinitialization_after_partial_approval_rejection(self):
        """Test re-initialization after admin1 approves and admin2 rejects"""
        # Initial approval setup with two admins
        approvers = [self.admin1, self.admin2]
        initiate_task_approval(self.task, approvers, self.staff_user)

        # Verify initial state
        self.assertEqual(TaskApproval.objects.filter(task=self.task).count(), 2)

        # Admin1 approves (forwarded to admin2)
        process_task_approval(self.task, self.admin1, "approved", "Looks good")

        # Verify forwarded state
        self.task.refresh_from_db()
        self.assertEqual(self.task.current_approval_step, 2)
        self.assertEqual(self.task.status, TaskStatus.FOR_CHECKING)

        # Admin2 rejects
        process_task_approval(self.task, self.admin2, "rejected", "Still needs work")

        # Verify rejection state
        self.task.refresh_from_db()
        self.assertFalse(self.task.requires_approval)
        self.assertEqual(self.task.current_approval_step, 0)
        self.assertEqual(self.task.status, TaskStatus.FOR_REVISION)

        # Try to re-initialize with same sequence - should NOT fail
        try:
            initiate_task_approval(self.task, approvers, self.staff_user)
            reinitialization_successful = True
        except Exception as e:
            reinitialization_successful = False
            self.fail(f"Re-initialization failed with error: {str(e)}")

        self.assertTrue(reinitialization_successful, "Re-initialization should succeed")

        # Verify re-initialized state
        self.task.refresh_from_db()
        self.assertTrue(self.task.requires_approval)
        self.assertEqual(self.task.current_approval_step, 1)
        self.assertEqual(self.task.status, TaskStatus.FOR_CHECKING)

        # Should have fresh approval records
        approval_records = TaskApproval.objects.filter(task=self.task, action="pending")
        self.assertEqual(approval_records.count(), 2)  # Both should be pending again

    def test_intermediate_approval_status_history_recording(self):
        """Test that intermediate approvals are recorded in status history"""
        # Setup approval workflow with two admins
        approvers = [self.admin1, self.admin2]
        initiate_task_approval(self.task, approvers, self.staff_user)

        # Get initial status history count
        initial_history_count = TaskStatusHistory.objects.filter(task=self.task).count()

        # Admin1 approves (this should create status history even though status stays FOR_CHECKING)
        process_task_approval(self.task, self.admin1, "approved", "First approval")

        # Check that status history was created for admin1's approval
        intermediate_history_count = TaskStatusHistory.objects.filter(
            task=self.task
        ).count()
        self.assertEqual(
            intermediate_history_count,
            initial_history_count + 1,
            "Intermediate approval should create status history",
        )

        # Verify the status history entry for admin1's approval
        admin1_history = TaskStatusHistory.objects.filter(
            task=self.task, change_type="approval", changed_by=self.admin1
        ).first()

        self.assertIsNotNone(
            admin1_history, "Admin1's approval should be recorded in status history"
        )
        self.assertEqual(admin1_history.old_status, TaskStatus.FOR_CHECKING)
        self.assertEqual(admin1_history.new_status, TaskStatus.FOR_CHECKING)
        self.assertIn("Approved by Admin One", admin1_history.remarks)
        self.assertIn("forwarded to Admin Two", admin1_history.remarks)

        # Admin2 rejects
        process_task_approval(self.task, self.admin2, "rejected", "Final rejection")

        # Check that both approvals are recorded in status history
        final_history_count = TaskStatusHistory.objects.filter(task=self.task).count()
        self.assertEqual(
            final_history_count,
            initial_history_count + 2,
            "Both intermediate approval and rejection should be recorded",
        )

        # Verify all approval-related actions are in history (initiation + admin1 approval + admin2 rejection)
        approval_history = TaskStatusHistory.objects.filter(
            task=self.task, change_type="approval"
        ).order_by("-created_at")

        self.assertEqual(
            approval_history.count(),
            3,
            "Should have 3 approval-related history entries: initiation, approval, rejection",
        )

        # Most recent should be admin2's rejection
        self.assertEqual(approval_history[0].changed_by, self.admin2)
        self.assertEqual(approval_history[0].new_status, TaskStatus.FOR_REVISION)
        self.assertIn("Rejected by Admin Two", approval_history[0].remarks)

        # Second should be admin1's approval
        self.assertEqual(approval_history[1].changed_by, self.admin1)
        self.assertEqual(approval_history[1].new_status, TaskStatus.FOR_CHECKING)
        self.assertIn("Approved by Admin One", approval_history[1].remarks)

        # Earliest should be workflow initiation
        self.assertEqual(approval_history[2].changed_by, self.staff_user)
        self.assertEqual(approval_history[2].new_status, TaskStatus.FOR_CHECKING)
        self.assertIn("Approval workflow initiated", approval_history[2].remarks)
