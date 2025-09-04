from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase

from core.choices import (
    ClientStatus,
    TaskCategory,
    TaskPriority,
    TaskStatus,
    TaxCaseCategory,
    TypeOfTaxCase,
    UserRoles,
)
from core.models import (
    AppLog,
    Client,
    ClientDocument,
    Notification,
    Task,
    TaskApproval,
    TaskStatusHistory,
    User,
)
from core.utils import get_today_local

User = get_user_model()


class UserModelTests(TestCase):
    """Test cases for User model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            first_name="John",
            middle_name="Doe",
            last_name="Smith",
            email="john@example.com",
            role=UserRoles.STAFF,
        )

    def test_fullname_property(self):
        """Test fullname property with all name parts"""
        self.assertEqual(self.user.fullname, "John Doe Smith")

    def test_fullname_property_no_middle_name(self):
        """Test fullname property without middle name"""
        user_no_middle = User.objects.create_user(
            username="nomiddle",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        self.assertEqual(user_no_middle.fullname, "Jane Doe")

    def test_fullname_property_only_first_name(self):
        """Test fullname property with only first name"""
        user_first_only = User.objects.create_user(
            username="firstonly",
            first_name="Bob",
            email="bob@example.com",
        )
        self.assertEqual(user_first_only.fullname, "Bob")

    def test_is_admin_property_staff(self):
        """Test is_admin property for staff user"""
        self.assertFalse(self.user.is_admin)

    def test_is_admin_property_admin(self):
        """Test is_admin property for admin user"""
        admin_user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            role=UserRoles.ADMIN,
        )
        self.assertTrue(admin_user.is_admin)

    def test_has_logs_property_no_logs(self):
        """Test has_logs property when user has no logs"""
        self.assertFalse(self.user.has_logs)

    def test_has_logs_property_with_logs(self):
        """Test has_logs property when user has logs"""
        from core.actions import create_log

        create_log(self.user, "Test log entry")
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_logs)

    def test_str_method(self):
        """Test string representation of User"""
        expected = f"#1 - testuser (John Doe Smith)"
        self.assertEqual(str(self.user), expected)


class ClientModelTests(TestCase):
    """Test cases for Client model functionality"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            role=UserRoles.ADMIN,
        )
        self.client = Client.objects.create(
            name="Test Client",
            contact_person="John Contact",
            email="client@example.com",
            phone="123-456-7890",
            address="123 Test Street",
            status=ClientStatus.ACTIVE,
            tin="123456789",
            notes="Test client notes",
            created_by=self.admin_user,
        )

    def test_is_active_property_active(self):
        """Test is_active property for active client"""
        self.assertTrue(self.client.is_active)

    def test_is_active_property_inactive(self):
        """Test is_active property for inactive client"""
        self.client.status = ClientStatus.INACTIVE
        self.client.save()
        self.assertFalse(self.client.is_active)

    def test_str_method(self):
        """Test string representation of Client"""
        self.assertEqual(str(self.client), "Test Client")


class TaskModelTests(TestCase):
    """Test cases for Task model functionality"""

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
        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.admin_user,
        )
        self.task = Task.objects.create(
            client=self.client,
            category=TaskCategory.COMPLIANCE,
            description="Test Task",
            status=TaskStatus.PENDING,
            assigned_to=self.staff_user,
            priority=TaskPriority.MEDIUM,
            deadline=get_today_local() + timedelta(days=7),
            period_covered="2025",
            engagement_date=get_today_local(),
        )

    def test_str_method(self):
        """Test string representation of Task"""
        expected = f"[{self.task.get_category_display()}] Test Task - {self.staff_user} ({self.task.status}, due {self.task.deadline.strftime('%b %d, %Y')})"
        self.assertEqual(str(self.task), expected)

    def test_pending_approver_no_approval(self):
        """Test pending_approver when task doesn't require approval"""
        self.assertIsNone(self.task.pending_approver)

    def test_pending_approver_with_approval(self):
        """Test pending_approver when task is in approval workflow"""
        from core.actions import initiate_task_approval

        self.task.status = TaskStatus.FOR_CHECKING
        self.task.requires_approval = True
        self.task.save()

        # Create approval record
        TaskApproval.objects.create(
            task=self.task,
            approver=self.admin_user,
            step_number=1,
            action="pending",
        )

        self.assertEqual(self.task.pending_approver, self.admin_user)

    def test_latest_remark_no_history(self):
        """Test latest_remark when no status history exists"""
        self.assertEqual(self.task.latest_remark, self.task.remarks)

    def test_latest_remark_with_history(self):
        """Test latest_remark with status history"""
        # Add status update with remark
        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks="Latest remark",
            changed_by=self.admin_user,
        )

        self.assertEqual(self.task.latest_remark, "Latest remark")

    def test_category_specific_fields_compliance(self):
        """Test category_specific_fields for compliance tasks"""
        self.task.steps = "Step 1, Step 2"
        self.task.requirements = "Requirement 1, Requirement 2"
        self.task.save()

        fields = self.task.category_specific_fields
        self.assertEqual(fields["Steps"], "Step 1, Step 2")
        self.assertEqual(fields["Requirements"], "Requirement 1, Requirement 2")

    def test_category_specific_fields_tax_case(self):
        """Test category_specific_fields for tax case tasks"""
        self.task.category = TaskCategory.TAX_CASE
        self.task.tax_category = TaxCaseCategory.ONE_TIME_ENGAGEMENT
        self.task.tax_type = TypeOfTaxCase.INCOME_TAX
        self.task.working_paper = "WP-2025-001"
        self.task.tax_payable = 50000.00
        self.task.save()

        fields = self.task.category_specific_fields
        self.assertEqual(fields["Tax Category"], "One-Time Engagement")
        self.assertEqual(fields["Tax Type"], "Income Tax")
        self.assertEqual(fields["Working Paper"], "WP-2025-001")
        self.assertEqual(fields["Tax Payable"], "₱50,000.00")

    def test_clean_compliance_valid(self):
        """Test clean method for valid compliance task"""
        try:
            self.task.full_clean()
        except ValidationError:
            self.fail("Task should be valid")

    def test_clean_compliance_missing_period(self):
        """Test clean method for compliance task missing period_covered"""
        self.task.period_covered = ""
        with self.assertRaises(ValidationError) as cm:
            self.task.full_clean()
        self.assertIn("period_covered", cm.exception.message_dict)

    def test_clean_compliance_missing_engagement_date(self):
        """Test clean method for compliance task missing engagement_date"""
        self.task.engagement_date = None
        with self.assertRaises(ValidationError) as cm:
            self.task.full_clean()
        self.assertIn("engagement_date", cm.exception.message_dict)

    def test_clean_tax_case_missing_period(self):
        """Test clean method for tax case missing period_covered"""
        self.task.category = TaskCategory.TAX_CASE
        self.task.period_covered = ""
        self.task.working_paper = "WP-2025-001"
        self.task.engagement_date = get_today_local()
        with self.assertRaises(ValidationError) as cm:
            self.task.full_clean()
        self.assertIn("period_covered", cm.exception.message_dict)

    def test_clean_tax_case_missing_working_paper(self):
        """Test clean method for tax case missing working_paper"""
        self.task.category = TaskCategory.TAX_CASE
        self.task.working_paper = ""
        with self.assertRaises(ValidationError) as cm:
            self.task.full_clean()
        self.assertIn("working_paper", cm.exception.message_dict)

    def test_add_status_update_creates_history(self):
        """Test that add_status_update creates status history"""
        initial_count = TaskStatusHistory.objects.count()

        self.task.add_status_update(
            new_status=TaskStatus.ON_GOING,
            remarks="Status update test",
            changed_by=self.admin_user,
        )

        self.assertEqual(TaskStatusHistory.objects.count(), initial_count + 1)
        history = TaskStatusHistory.objects.first()
        self.assertEqual(history.old_status, TaskStatus.PENDING)
        self.assertEqual(history.new_status, TaskStatus.ON_GOING)
        self.assertEqual(history.remarks, "Status update test")

    def test_add_status_update_same_status_no_history(self):
        """Test that add_status_update doesn't create history for same status"""
        initial_count = TaskStatusHistory.objects.count()

        self.task.add_status_update(
            new_status=TaskStatus.PENDING,  # Same as current
            remarks="Same status test",
            changed_by=self.admin_user,
        )

        self.assertEqual(TaskStatusHistory.objects.count(), initial_count)


class NotificationModelTests(TestCase):
    """Test cases for Notification model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
        )
        self.notification = Notification.objects.create(
            recipient=self.user,
            title="Test Notification",
            message="This is a test notification",
            link="/test-link",
        )

    def test_str_method_unread(self):
        """Test string representation of unread notification"""
        expected = f"[Unread] Test Notification for {self.user.fullname}"
        self.assertEqual(str(self.notification), expected)

    def test_str_method_read(self):
        """Test string representation of read notification"""
        self.notification.is_read = True
        expected = f"[Read] Test Notification for {self.user.fullname}"
        self.assertEqual(str(self.notification), expected)

    def test_str_method_no_recipient(self):
        """Test string representation with no recipient"""
        notification_no_recipient = Notification.objects.create(
            title="System Notification",
            message="System message",
        )
        expected = "[Unread] System Notification for No Recipient"
        self.assertEqual(str(notification_no_recipient), expected)

    def test_mark_as_read(self):
        """Test mark_as_read method"""
        self.assertFalse(self.notification.is_read)
        self.notification.mark_as_read()
        self.assertTrue(self.notification.is_read)

    def test_timesince_created(self):
        """Test timesince_created property"""
        # This should return a string like "0 minutes ago"
        timesince = self.notification.timesince_created
        self.assertIsInstance(timesince, str)
        self.assertIn("ago", timesince)

    def test_get_full_link_with_link(self):
        """Test get_full_link property with link"""
        # This would require FRONTEND_URL setting
        link = self.notification.get_full_link
        self.assertIsNotNone(link)

    def test_get_full_link_no_link(self):
        """Test get_full_link property without link"""
        notification_no_link = Notification.objects.create(
            recipient=self.user,
            title="No Link",
            message="No link test",
        )
        self.assertIsNone(notification_no_link.get_full_link)


class ClientDocumentModelTests(TestCase):
    """Test cases for ClientDocument model functionality"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            role=UserRoles.ADMIN,
        )
        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.admin_user,
        )
        self.test_file = ContentFile(b"Test file content", name="test_document.pdf")
        self.document = ClientDocument.objects.create(
            client=self.client,
            title="Test Document",
            description="A test document",
            document_file=self.test_file,
            uploaded_by=self.admin_user,
        )

    def test_str_method(self):
        """Test string representation of ClientDocument"""
        expected = f"Test Document - {self.client.name}"
        self.assertEqual(str(self.document), expected)

    def test_file_size_property(self):
        """Test file_size property"""
        size = self.document.file_size
        self.assertIsInstance(size, str)
        # Should contain size information or "File not found"
        self.assertTrue(
            "B" in size
            or "KB" in size
            or "MB" in size
            or "GB" in size
            or "File not found" in size
        )

    def test_file_extension_property_pdf(self):
        """Test file_extension property for PDF"""
        self.assertEqual(self.document.file_extension, "PDF")

    def test_file_extension_property_no_extension(self):
        """Test file_extension property for file without extension"""
        file_no_ext = ContentFile(b"Content", name="file_no_extension")
        doc_no_ext = ClientDocument.objects.create(
            client=self.client,
            title="No Extension",
            document_file=file_no_ext,
            uploaded_by=self.admin_user,
        )
        self.assertEqual(doc_no_ext.file_extension, "Unknown")

    def test_file_exists(self):
        """Test file_exists method"""
        exists = self.document.file_exists()
        self.assertIsInstance(exists, bool)


class AppLogModelTests(TestCase):
    """Test cases for AppLog model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
        )
        self.log = AppLog.objects.create(
            user=self.user,
            details="Test log entry",
        )

    def test_str_method(self):
        """Test string representation of AppLog"""
        expected = (
            f"{self.user.fullname} - Test log entry - {self.log.created_at.date()}"
        )
        self.assertEqual(str(self.log), expected)

    def test_str_method_no_user(self):
        """Test string representation without user"""
        log_no_user = AppLog.objects.create(details="System log")
        expected = f"No User - System log - {log_no_user.created_at.date()}"
        self.assertEqual(str(log_no_user), expected)


class TaskStatusHistoryModelTests(TestCase):
    """Test cases for TaskStatusHistory model functionality"""

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
        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.admin_user,
        )
        self.task = Task.objects.create(
            client=self.client,
            category=TaskCategory.COMPLIANCE,
            description="Test Task",
            status=TaskStatus.PENDING,
            assigned_to=self.staff_user,
            deadline=get_today_local() + timedelta(days=7),
        )

    def test_str_method(self):
        """Test string representation of TaskStatusHistory"""
        history = TaskStatusHistory.objects.create(
            task=self.task,
            old_status=TaskStatus.PENDING,
            new_status=TaskStatus.ON_GOING,
            changed_by=self.admin_user,
            remarks="Status change test",
        )

        expected = f"Test Task | Pending → On Going by {self.admin_user.fullname}"
        self.assertEqual(str(history), expected)

    def test_formatted_date_property(self):
        """Test formatted_date property"""
        history = TaskStatusHistory.objects.create(
            task=self.task,
            old_status=TaskStatus.PENDING,
            new_status=TaskStatus.ON_GOING,
            changed_by=self.admin_user,
        )

        formatted_date = history.formatted_date
        self.assertIsInstance(formatted_date, str)
        # Should contain time format
        self.assertRegex(formatted_date, r"\d{1,2}:\d{2} [AP]M")


class TaskApprovalModelTests(TestCase):
    """Test cases for TaskApproval model functionality"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            role=UserRoles.ADMIN,
        )
        self.client = Client.objects.create(
            name="Test Client",
            created_by=self.admin_user,
        )
        self.task = Task.objects.create(
            client=self.client,
            category=TaskCategory.COMPLIANCE,
            description="Test Task",
            status=TaskStatus.FOR_CHECKING,
            assigned_to=self.admin_user,
            deadline=get_today_local() + timedelta(days=7),
            period_covered="2025",
            engagement_date=get_today_local(),
            requires_approval=True,
        )

    def test_str_method(self):
        """Test string representation of TaskApproval"""
        approval = TaskApproval.objects.create(
            task=self.task,
            approver=self.admin_user,
            step_number=1,
            action="pending",
        )

        expected = (
            f"Step 1: {self.admin_user.fullname} - Pending Review for {self.task}"
        )
        self.assertEqual(str(approval), expected)
