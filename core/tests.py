from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from decimal import Decimal

from core.actions import initiate_task_approval, process_task_approval
from core.choices import (
    TaskCategory, 
    TaskStatus, 
    UserRoles, 
    TaskPriority,
    ClientStatus,
    TaxCaseCategory,
    TypeOfTaxCase
)
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
        self.today = get_today_local()

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
            priority=TaskPriority.HIGH,
            period_covered="2025",
            engagement_date=self.today - timedelta(days=10),
            last_update=self.today - timedelta(days=1),
        )

        # Overdue task
        Task.objects.create(
            client=self.active_client,
            assigned_to=self.staff_user,
            category=TaskCategory.TAX_CASE,
            description="Overdue Tax Case",
            deadline=self.today - timedelta(days=10),
            status=TaskStatus.ON_GOING,
            priority=TaskPriority.HIGH,
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
            priority=TaskPriority.MEDIUM,
            requires_approval=True,
            current_approval_step=1,
            period_covered="2025",
            engagement_date=self.today - timedelta(days=5),
            last_update=self.today - timedelta(days=1),
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
            'summary', 'charts_data', 'performance_metrics',
            'team_analytics', 'client_insights', 'business_intelligence',
            'quick_actions', 'metadata'
        ]
        
        for section in required_sections:
            self.assertIn(section, data, f"Missing required section: {section}")

    def test_summary_statistics_accuracy(self):
        """Test accuracy of summary statistics calculations"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        data = response.data
        summary = data['summary']
        
        # Test basic counts
        self.assertEqual(summary['total'], 3)
        self.assertEqual(summary['completed'], 1)
        self.assertEqual(summary['in_progress'], 1)
        self.assertEqual(summary['for_checking'], 1)
        
        # Test priority distribution
        self.assertEqual(summary['high_priority'], 2)
        self.assertEqual(summary['medium_priority'], 1)
        
        # Test overdue tasks
        self.assertEqual(summary['overdue'], 1)

    def test_charts_data_structure(self):
        """Test charts data structure for visualization"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        charts_data = response.data['charts_data']
        
        # Test required chart data sections
        self.assertIn('category_distribution', charts_data)
        self.assertIn('weekly_trends', charts_data)
        self.assertIn('status_breakdown', charts_data)
        self.assertIn('priority_breakdown', charts_data)
        
        # Test weekly trends structure
        weekly_trends = charts_data['weekly_trends']
        self.assertIsInstance(weekly_trends, list)
        self.assertEqual(len(weekly_trends), 8)  # 8 weeks of data

    def test_performance_metrics_calculations(self):
        """Test performance metrics calculations"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        performance = response.data['performance_metrics']
        
        # Test required calculated metrics per specification
        required_metrics = [
            'overall_completion_rate', 'on_time_completion_rate',
            'workload_balance_score', 'average_completion_days'
        ]
        
        for metric in required_metrics:
            self.assertIn(metric, performance)
            self.assertIsInstance(performance[metric], (int, float))

    def test_business_intelligence_data(self):
        """Test business intelligence metrics"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        bi_data = response.data['business_intelligence']
        
        # Test approval workflow tracking
        self.assertIn('approval_workflow', bi_data)
        approval = bi_data['approval_workflow']
        self.assertEqual(approval['pending_my_approval'], 1)  # Admin has 1 pending
        
        # Test tax analysis
        self.assertIn('tax_analysis', bi_data)
        tax_analysis = bi_data['tax_analysis']
        if tax_analysis:
            self.assertIn('tax_payable_total', tax_analysis)
            self.assertEqual(tax_analysis['tax_payable_total'], 50000.0)

    def test_role_based_data_filtering(self):
        """Test data filtering based on user role"""
        # Test admin sees all data
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        admin_data = response.data
        self.assertEqual(admin_data['summary']['total'], 3)
        self.assertEqual(admin_data['metadata']['data_scope'], 'all_tasks')
        
        # Test staff sees only assigned tasks
        self._authenticate_user(self.staff_user)
        response = self.api_client.get(url)
        
        staff_data = response.data
        staff_task_count = Task.objects.filter(assigned_to=self.staff_user).count()
        self.assertEqual(staff_data['summary']['total'], staff_task_count)
        self.assertEqual(staff_data['metadata']['data_scope'], 'assigned_tasks')

    def test_metadata_information(self):
        """Test metadata for dashboard functionality"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        metadata = response.data['metadata']
        
        # Test required metadata fields per specification
        required_fields = ['generated_at', 'user_role', 'is_admin', 'data_scope']
        for field in required_fields:
            self.assertIn(field, metadata)
        
        # Test metadata values
        self.assertEqual(metadata['user_role'], UserRoles.ADMIN)
        self.assertTrue(metadata['is_admin'])
        self.assertEqual(metadata['generated_at'], self.today.isoformat())

    def test_error_handling(self):
        """Test robust error handling with edge cases"""
        # Store original task count
        original_task_count = Task.objects.count()
        
        # Test with empty database
        Task.objects.all().delete()
        
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        response = self.api_client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        # Should still have all required sections
        required_sections = [
            'summary', 'charts_data', 'performance_metrics',
            'team_analytics', 'client_insights', 'business_intelligence',
            'quick_actions', 'metadata'
        ]
        
        for section in required_sections:
            self.assertIn(section, data)
        
        # Summary should have zero counts
        self.assertEqual(data['summary']['total'], 0)

    def test_field_name_verification(self):
        """Test correct model field names to avoid FieldError"""
        self._authenticate_user(self.admin_user)
        url = self.STATISTICS_URL
        
        # Should not raise any FieldError exceptions
        try:
            response = self.api_client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        except Exception as e:
            self.fail(f"Statistics endpoint raised an exception: {str(e)}")
