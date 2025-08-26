from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Case, Value, When
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _

from core.choices import (
    BirForms,
    ClientStatus,
    TaskCategory,
    TaskPriority,
    TaskStatus,
    TaxCaseCategory,
    TypeOfTaxCase,
    UserRoles,
)
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
        return f"{self.first_name} {self.middle_name} {self.last_name}".title()

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
    status_history = models.JSONField(default=list, blank=True)

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

    def add_status_update(self, status, remarks):
        self.last_update = get_now_local()
        self.status_history.insert(
            0,
            {"status": status, "remarks": remarks, "date": get_now_local().isoformat()},
        )
        self.save(update_fields=["status_history", "last_update"])

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


class AppLog(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="logs"
    )
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.fullname} - {self.details[:50]} - {self.created_at.date()}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "App Log"
        verbose_name_plural = "App Logs"
