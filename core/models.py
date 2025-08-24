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
    TaskPriority,
    TaskStatus,
    TaxCaseCategory,
    TypeOfTaxCase,
    UserRoles,
)
from core.utils import get_today_local


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


class Compliance(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    description = models.CharField(max_length=255)
    steps = models.CharField(max_length=255, blank=True, null=True)
    requirements = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    period_covered = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='compliances_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"{self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"


class FinancialStatementPreparation(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    type = models.CharField(max_length=255)
    needed_data = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='financial_statement_preparations_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return (
            f"{self.type[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"
        )


class AccountingAudit(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    description = models.CharField(max_length=255)
    period_covered = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='accounting_audits_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"{self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"


class FinanceImplementation(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    description = models.CharField(max_length=255)
    period_covered = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='finance_implementations_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"{self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"


class HumanResourceImplementation(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    description = models.CharField(max_length=255)
    period_covered = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='human_resource_implementations_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"{self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"


class MiscellaneousTasks(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    area = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    period_covered = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='miscellaneous_tasks_assigned_to')
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        deadline_str = (
            self.deadline.strftime("%b %d, %Y") if self.deadline else "No deadline"
        )
        return f"{self.description[:30]} - {self.assigned_to} ({self.status}, due {deadline_str})"


class TaxCase(models.Model):
    client = models.ForeignKey(Client, on_delete=models.RESTRICT)
    category = models.CharField(
        max_length=3,
        choices=TaxCaseCategory.choices,
        default=None,
        blank=True,
        null=True,
    )
    type = models.CharField(
        max_length=2,
        choices=TypeOfTaxCase.choices,
        default=None,
        blank=True,
        null=True,
    )
    form = models.CharField(
        max_length=6,
        choices=BirForms.choices,
        default=None,
        blank=True,
        null=True,
    )
    period_covered = models.CharField(max_length=255)
    working_paper = models.CharField(max_length=255)
    tax_payable = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
    )
    last_followup = models.DateField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='tax_cases_assigned_to')
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_YET_STARTED
    )
    priority = models.CharField(
        max_length=6, choices=TaskPriority.choices, default=TaskPriority.MEDIUM
    )
    engagement_date = models.DateField()
    deadline = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    date_complied = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.category} - {self.type} for {self.client.name} ({self.status})"


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