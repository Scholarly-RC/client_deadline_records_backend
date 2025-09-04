from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Case, Value, When
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _

from core.choices import (BirForms, ClientStatus, TaskCategory, TaskPriority,
                          TaskStatus, TaxCaseCategory, TypeOfTaxCase,
                          UserRoles)
from core.utils import get_now_local, get_today_local


class User(AbstractUser):
    middle_name = models.CharField(_("Middle Name"), max_length=150, blank=True)
    role = models.CharField(
        max_length=5,
        choices=UserRoles.choices,
        default=UserRoles.STAFF,
    )
    updated = models.DateField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["role", "first_name"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"#{self.pk} - {self.username} ({self.fullname})"

    @property
    def fullname(self):
        """Return formatted full name without extra spaces for empty middle name"""
        name_parts = [self.first_name, self.middle_name, self.last_name]
        # Filter out empty parts and join with spaces
        return " ".join(part for part in name_parts if part.strip()).title()

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def has_logs(self):
        return self.logs.exists()


class Client(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ClientStatus.choices, default=ClientStatus.ACTIVE
    )
    tin = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="clients_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    @property
    def is_active(self):
        return self.status == "active"


class TaskStatusHistory(models.Model):
    task = models.ForeignKey(
        "Task", on_delete=models.CASCADE, related_name="status_history_records"
    )
    old_status = models.CharField(
        max_length=20, choices=TaskStatus.choices, null=True, blank=True
    )
    new_status = models.CharField(max_length=20, choices=TaskStatus.choices)
    changed_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="status_changes_made"
    )
    remarks = models.TextField(blank=True, null=True)

    # Additional context fields
    change_type = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual Update"),
            ("approval", "Approval Process"),
            ("system", "System Update"),
        ],
        default="manual",
    )

    # For approval-related status changes
    related_approval = models.ForeignKey(
        "TaskApproval",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Task Status History"
        verbose_name_plural = "Task Status Histories"
        indexes = [
            models.Index(fields=["task", "-created_at"]),
            models.Index(fields=["changed_by", "-created_at"]),
        ]

    def __str__(self):
        old_status_display = self.get_old_status_display() if self.old_status else "New"
        return f"{self.task.description[:30]} | {old_status_display} → {self.get_new_status_display()} by {self.changed_by.fullname}"

    @property
    def formatted_date(self):
        return self.created_at.strftime("%b %d, %Y at %I:%M %p")


class TaskApproval(models.Model):
    APPROVAL_ACTIONS = [
        ("approved", "Approved"),
        ("rejected", "Rejected/For Revision"),
        ("pending", "Pending Review"),
    ]

    task = models.ForeignKey("Task", on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="task_approvals_given"
    )
    action = models.CharField(
        max_length=10, choices=APPROVAL_ACTIONS, default="pending"
    )
    comments = models.TextField(blank=True, null=True)
    step_number = models.PositiveIntegerField(default=1)
    next_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_approvals",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["task", "approver", "step_number"]
        indexes = [
            models.Index(fields=["task", "step_number"]),
            models.Index(fields=["approver", "action"]),
        ]

    def __str__(self):
        return f"Step {self.step_number}: {self.approver.fullname} - {self.get_action_display()} for {self.task}"


class Task(models.Model):
    # Common fields
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    category = models.CharField(max_length=25, choices=TaskCategory.choices)
    description = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="tasks_assigned_to"
    )
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    # New approval-related fields
    current_approval_step = models.PositiveIntegerField(default=0)
    requires_approval = models.BooleanField(default=False)

    # Fields that apply to most categories
    period_covered = models.CharField(max_length=255, blank=True, null=True)
    engagement_date = models.DateField(blank=True, null=True)

    # Category-specific fields
    # Compliance specific
    steps = models.CharField(max_length=255, blank=True, null=True)
    requirements = models.CharField(max_length=255, blank=True, null=True)

    # Financial Statement specific
    type = models.CharField(max_length=255, blank=True, null=True)
    needed_data = models.CharField(max_length=255, blank=True, null=True)

    # Miscellaneous Tasks specific
    area = models.CharField(max_length=255, blank=True, null=True)

    # Tax Case specific
    tax_category = models.CharField(
        max_length=3,
        choices=TaxCaseCategory.choices,
        blank=True,
        null=True,
    )
    tax_type = models.CharField(
        max_length=2,
        choices=TypeOfTaxCase.choices,
        blank=True,
        null=True,
    )
    form = models.CharField(
        max_length=6,
        choices=BirForms.choices,
        blank=True,
        null=True,
    )
    working_paper = models.CharField(max_length=255, blank=True, null=True)
    tax_payable = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    last_followup = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "tasks"
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["assigned_to", "deadline"]),
            models.Index(fields=["client", "category"]),
        ]

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"[{self.get_category_display()}] {self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"

    def add_status_update(
        self,
        new_status,
        remarks=None,
        changed_by=None,
        change_type="manual",
        related_approval=None,
        force_history=False,
    ):
        """Add a status change record to the history

        Args:
            new_status: The new status to set
            remarks: Optional remarks for the change
            changed_by: User who made the change
            change_type: Type of change (manual, approval, system)
            related_approval: TaskApproval instance if this is approval-related
            force_history: If True, creates status history even if status doesn't change
                           (useful for approval workflows where multiple approvers
                           handle the same status)
        """
        from core.actions import create_log

        old_status = self.status

        # Create status history entry if status changed OR if forced (for approval workflows)
        if old_status != new_status or force_history:
            # Only update status if it actually changed
            if old_status != new_status:
                self.status = new_status
                self.last_update = get_now_local()
                update_fields = ["status", "last_update"]
            else:
                # Status didn't change but we're forcing history creation
                self.last_update = get_now_local()
                update_fields = ["last_update"]

            # Create status history record
            TaskStatusHistory.objects.create(
                task=self,
                old_status=old_status,
                new_status=new_status,
                changed_by=changed_by,
                remarks=remarks,
                change_type=change_type,
                related_approval=related_approval,
            )

            # Always update task remarks to the latest remark if provided
            if remarks and remarks.strip():
                self.remarks = remarks
                update_fields.append("remarks")

            self.save(update_fields=update_fields)

            # Log the status change
            if changed_by:
                from core.actions import create_log

                old_status_display = self.get_status_display() if old_status else "New"
                new_status_display = self.get_status_display()
                log_message = f"Task status changed: '{self.description}' from {old_status_display} to {new_status_display}"
                if remarks:
                    log_message += f" - {remarks}"
                create_log(changed_by, log_message)
        else:
            # If status didn't change and no force_history, still update remarks if provided
            if remarks and remarks.strip():
                self.remarks = remarks
                self.last_update = get_now_local()
                self.save(update_fields=["remarks", "last_update"])

    @property
    def pending_approver(self):
        """Get the current pending approver for this task"""
        if self.status == TaskStatus.FOR_CHECKING and self.requires_approval:
            pending_approval = (
                self.approvals.filter(action="pending").order_by("step_number").first()
            )
            return pending_approval.approver if pending_approval else None
        return None

    @property
    def latest_remark(self):
        """Get the latest remark from status history

        Returns the most recent remark from status history,
        regardless of whether it's user-generated or system-generated.
        """
        latest_history = (
            self.status_history_records.exclude(remarks__isnull=True)
            .exclude(remarks__exact="")
            .order_by("-created_at")
            .first()
        )
        return latest_history.remarks if latest_history else self.remarks

    def clean(self):
        """Validate category-specific required fields"""
        from django.core.exceptions import ValidationError

        if self.category == TaskCategory.COMPLIANCE:
            if not self.period_covered:
                raise ValidationError(
                    {
                        "period_covered": "Period covered is required for compliance tasks."
                    }
                )
            if not self.engagement_date:
                raise ValidationError(
                    {
                        "engagement_date": "Engagement date is required for compliance tasks."
                    }
                )

        elif self.category == TaskCategory.FINANCIAL_STATEMENT:
            if not self.type:
                raise ValidationError(
                    {"type": "Type is required for financial statement tasks."}
                )
            if not self.needed_data:
                raise ValidationError(
                    {
                        "needed_data": "Needed data is required for financial statement tasks."
                    }
                )

        elif self.category == TaskCategory.TAX_CASE:
            if not self.period_covered:
                raise ValidationError(
                    {"period_covered": "Period covered is required for tax cases."}
                )
            if not self.working_paper:
                raise ValidationError(
                    {"working_paper": "Working paper is required for tax cases."}
                )
            if not self.engagement_date:
                raise ValidationError(
                    {"engagement_date": "Engagement date is required for tax cases."}
                )

        elif self.category == TaskCategory.MISCELLANEOUS:
            if not self.area:
                raise ValidationError(
                    {"area": "Area is required for miscellaneous tasks."}
                )
            if not self.period_covered:
                raise ValidationError(
                    {
                        "period_covered": "Period covered is required for miscellaneous tasks."
                    }
                )
            if not self.engagement_date:
                raise ValidationError(
                    {
                        "engagement_date": "Engagement date is required for miscellaneous tasks."
                    }
                )

        elif self.category in [
            TaskCategory.ACCOUNTING_AUDIT,
            TaskCategory.FINANCE_IMPLEMENTATION,
            TaskCategory.HR_IMPLEMENTATION,
        ]:
            if not self.period_covered:
                raise ValidationError(
                    {
                        "period_covered": "Period covered is required for this task category."
                    }
                )
            if not self.engagement_date:
                raise ValidationError(
                    {
                        "engagement_date": "Engagement date is required for this task category."
                    }
                )

    @property
    def category_specific_fields(self):
        """Return a dictionary of non-empty category-specific fields"""
        fields = {}

        if self.category == TaskCategory.COMPLIANCE:
            if self.steps:
                fields["Steps"] = self.steps
            if self.requirements:
                fields["Requirements"] = self.requirements

        elif self.category == TaskCategory.FINANCIAL_STATEMENT:
            if self.type:
                fields["Type"] = self.type
            if self.needed_data:
                fields["Needed Data"] = self.needed_data

        elif self.category == TaskCategory.MISCELLANEOUS:
            if self.area:
                fields["Area"] = self.area

        elif self.category == TaskCategory.TAX_CASE:
            if self.tax_category:
                fields["Tax Category"] = self.get_tax_category_display()
            if self.tax_type:
                fields["Tax Type"] = self.get_tax_type_display()
            if self.form:
                fields["Form"] = self.get_form_display()
            if self.working_paper:
                fields["Working Paper"] = self.working_paper
            if self.tax_payable:
                fields["Tax Payable"] = f"₱{self.tax_payable:,.2f}"
            if self.last_followup:
                fields["Last Followup"] = self.last_followup.strftime("%b %d, %Y")

        return fields


class Notification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, related_name="notifications"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        recipient = self.recipient.fullname if self.recipient else "No Recipient"
        return f"[{'Read' if self.is_read else 'Unread'}] {self.title} for {recipient}"

    def mark_as_read(self):
        self.is_read = True
        self.save()

    @property
    def timesince_created(self):
        return f"{timesince(self.created_at)} ago"

    @property
    def get_full_link(self):
        return f"{settings.FRONTEND_URL}/{self.link}" if self.link else None


class ClientDocument(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_file = models.FileField(upload_to="client_documents/")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="uploaded_documents"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.client.name}"

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Client Document"
        verbose_name_plural = "Client Documents"

    def soft_delete(self):
        """Soft delete the document by moving file to deleted directory"""
        if not self.is_deleted:
            from django.core.files.storage import default_storage
            from django.utils import timezone

            # Generate new path for deleted file
            original_path = self.document_file.name or ""
            filename = (
                original_path.split("/")[-1]
                if original_path and "/" in original_path
                else (original_path or "unknown_file")
            )
            deleted_path = (
                f"deleted/{timezone.now().strftime('%Y/%m/%d')}/{self.pk}_{filename}"
            )

            try:
                # Check if file exists before attempting to move
                if original_path and default_storage.exists(original_path):
                    # Read the original file
                    with default_storage.open(original_path, "rb") as old_file:
                        file_content = old_file.read()

                    # Save to new location
                    default_storage.save(deleted_path, ContentFile(file_content))

                    # Delete original file
                    default_storage.delete(original_path)

                    # Update model fields
                    self.document_file.name = deleted_path
                    self.is_deleted = True
                    self.deleted_at = timezone.now()
                    self.save(
                        update_fields=["document_file", "is_deleted", "deleted_at"]
                    )

                    return True
                else:
                    # File doesn't exist, just mark as deleted
                    self.is_deleted = True
                    self.deleted_at = timezone.now()
                    self.save(update_fields=["is_deleted", "deleted_at"])
                    return True

            except Exception as e:
                # If moving fails, still mark as deleted but keep original path
                self.is_deleted = True
                self.deleted_at = timezone.now()
                self.save(update_fields=["is_deleted", "deleted_at"])
                return False

        return True

    def file_exists(self):
        """Check if the file exists in storage"""
        try:
            return bool(
                self.document_file
                and self.document_file.name
                and self.document_file.storage.exists(self.document_file.name)
            )
        except Exception:
            return False

    def restore(self):
        """Restore a soft-deleted document"""
        if self.is_deleted:
            from django.core.files.storage import default_storage
            from django.utils import timezone

            # Generate original path
            deleted_path = self.document_file.name or ""
            if deleted_path and "/" in deleted_path:
                filename_with_id = deleted_path.split("/")[-1]
                if "_" in filename_with_id:
                    original_filename = filename_with_id.split("_", 1)[
                        -1
                    ]  # Remove ID prefix
                else:
                    original_filename = filename_with_id
            else:
                original_filename = deleted_path or "unknown_file"
            original_path = f"client_documents/{original_filename}"

            try:
                # Check if file exists in deleted location before attempting to move
                if deleted_path and default_storage.exists(deleted_path):
                    # Read the deleted file
                    with default_storage.open(deleted_path, "rb") as deleted_file:
                        file_content = deleted_file.read()

                    # Save to original location
                    default_storage.save(original_path, ContentFile(file_content))

                    # Delete from deleted location
                    default_storage.delete(deleted_path)

                    # Update model fields
                    self.document_file.name = original_path
                    self.is_deleted = False
                    self.deleted_at = None
                    self.save(
                        update_fields=["document_file", "is_deleted", "deleted_at"]
                    )

                    return True
                else:
                    # File doesn't exist in deleted location, just mark as restored
                    self.document_file.name = original_path
                    self.is_deleted = False
                    self.deleted_at = None
                    self.save(
                        update_fields=["document_file", "is_deleted", "deleted_at"]
                    )
                    return True

            except Exception as e:
                # If restoring fails, still mark as restored
                self.is_deleted = False
                self.deleted_at = None
                self.save(update_fields=["is_deleted", "deleted_at"])
                return False

        return True

    def hard_delete(self):
        """Permanently delete the document and its file"""
        if self.document_file:
            self.document_file.delete(save=False)
        super().delete()

    @property
    def file_size(self):
        """Return file size in human readable format"""
        try:
            if (
                self.document_file
                and self.document_file.name
                and self.document_file.storage.exists(self.document_file.name)
            ):
                size = self.document_file.size
                if size:
                    for unit in ["B", "KB", "MB", "GB"]:
                        if size < 1024.0:
                            return f"{size:.1f} {unit}"
                        size /= 1024.0
            return "File not found"
        except Exception:
            return "Unknown"

    @property
    def file_extension(self):
        """Return file extension"""
        try:
            if self.document_file and self.document_file.name:
                name_parts = self.document_file.name.split(".")
                if len(name_parts) > 1:
                    return name_parts[-1].upper()
            return "Unknown"
        except Exception:
            return "Unknown"


class AppLog(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="logs"
    )
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_name = self.user.fullname if self.user else "No User"
        return f"{user_name} - {self.details[:50]} - {self.created_at.date()}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "App Log"
        verbose_name_plural = "App Logs"
