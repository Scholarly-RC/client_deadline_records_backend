from django.contrib.auth import get_user_model
from django.test import TestCase

from core.actions import initiate_task_approval, process_task_approval
from core.choices import TaskCategory, TaskStatus, UserRoles
from core.models import Client, Task, TaskApproval, TaskStatusHistory
from core.utils import get_today_local

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
        original_task_remarks = self.task.remarks

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

    def test_api_endpoint_scenario_remarks_behavior(self):
        """Test the exact scenario from the user's API endpoint example"""
        # Simulate the exact scenario from the API endpoint data
        # 1. Start with "Not Yet Started" and user remark "Vwqeqwe"
        user_remark = "Vwqeqwe"
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,  # "Not Yet Started" -> "On Going"
            remarks=user_remark,
            changed_by=self.staff_user,  # "Aiko Lareina Sullivan Rosas"
            change_type="manual",
        )

        # Verify initial state
        self.task.refresh_from_db()
        self.assertEqual(self.task.remarks, user_remark)

        # 2. Initiate approval workflow ("On Going" -> "For Checking")
        initiate_task_approval(self.task, [self.admin1], self.staff_user)

        # Task remarks should now show workflow initiation message
        self.task.refresh_from_db()
        self.assertIn(
            "Approval workflow initiated with 1 approver(s): Admin One",
            self.task.remarks,
        )

        # 3. Admin approves and completes ("For Checking" -> "Completed")
        admin_comment = "Raguy"
        process_task_approval(self.task, self.admin1, "approved", admin_comment)

        # Task remarks should now show the completion message (latest remark)
        # This should match: "Approved and completed by Charles Andrew Barsubia. Comments: Raguy"
        self.task.refresh_from_db()
        expected_completion_message = f"Approved and completed by {self.admin1.fullname}. Comments: {admin_comment}"
        self.assertEqual(self.task.remarks, expected_completion_message)

        # Verify this is indeed the latest remark in status history
        latest_history = (
            TaskStatusHistory.objects.filter(task=self.task)
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(latest_history.remarks, expected_completion_message)
        self.assertEqual(latest_history.new_status, TaskStatus.COMPLETED)

        # Verify the complete status history matches the API example structure
        status_history = TaskStatusHistory.objects.filter(task=self.task).order_by(
            "-created_at"
        )

        # Should have 3 entries: completion, workflow initiation, initial user update
        self.assertEqual(status_history.count(), 3)

        # Latest: completion
        completion_entry = status_history[0]
        self.assertEqual(completion_entry.old_status, TaskStatus.FOR_CHECKING)
        self.assertEqual(completion_entry.new_status, TaskStatus.COMPLETED)
        self.assertEqual(completion_entry.changed_by, self.admin1)
        self.assertIn("Approved and completed", completion_entry.remarks)
        self.assertIn(admin_comment, completion_entry.remarks)

        # Middle: workflow initiation
        workflow_entry = status_history[1]
        self.assertEqual(workflow_entry.old_status, TaskStatus.ON_GOING)
        self.assertEqual(workflow_entry.new_status, TaskStatus.FOR_CHECKING)
        self.assertEqual(workflow_entry.changed_by, self.staff_user)
        self.assertIn("Approval workflow initiated", workflow_entry.remarks)

        # Earliest: user update
        user_entry = status_history[2]
        self.assertEqual(user_entry.old_status, TaskStatus.PENDING)  # Initial status
        self.assertEqual(user_entry.new_status, TaskStatus.ON_GOING)
        self.assertEqual(user_entry.changed_by, self.staff_user)
        self.assertEqual(user_entry.remarks, user_remark)
