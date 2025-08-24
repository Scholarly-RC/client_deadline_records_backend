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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT)
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


class DeadlineType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_reminder_days = models.PositiveIntegerField(default=7)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Deadline Type"
        verbose_name_plural = "Deadline Types"


class ClientDeadline(models.Model):
    PRIORITY_CHOICES = [
        (5, "Highest"),
        (4, "High"),
        (3, "Medium"),
        (2, "Low"),
        (1, "Lowest"),
    ]

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("pending", "Pending"),
        ("overdue", "Overdue"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.RESTRICT, related_name="deadlines"
    )
    deadline_type = models.ForeignKey(DeadlineType, on_delete=models.RESTRICT)
    due_date = models.DateField()
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.TextField(blank=True)
    reminder_date = models.DateField(blank=True, null=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="assigned_deadlines",
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="deadlines_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client.name} - {self.deadline_type.name} - {self.due_date}"

    def save(self, *args, **kwargs):
        # Auto-set reminder date
        self.reminder_date = self.due_date - timezone.timedelta(
            days=self.deadline_type.default_reminder_days
        )

        if self.due_date < get_today_local() and self.status == "pending":
            self.status = "overdue"
        elif self.due_date > get_today_local() and self.status == "overdue":
            self.status = "pending"

        super().save(*args, **kwargs)

    class Meta:
        ordering = [
            Case(
                When(status="in_progress", then=Value(0)),
                When(status="pending", then=Value(1)),
                When(status="overdue", then=Value(2)),
                When(status="completed", then=Value(3)),
                When(status="cancelled", then=Value(4)),
                default=Value(5),
            ),
            "due_date",
            "-priority",
        ]
        verbose_name = "Client Deadline"
        verbose_name_plural = "Client Deadlines"


class WorkUpdate(models.Model):
    deadline = models.ForeignKey(
        ClientDeadline, on_delete=models.CASCADE, related_name="work_updates"
    )
    status = models.CharField(max_length=20, choices=ClientDeadline.STATUS_CHOICES)
    notes = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="work_updates_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Update for {self.deadline} by {self.created_by}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Work Update"
        verbose_name_plural = "Work Updates"


class ClientDocument(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.RESTRICT, related_name="documents"
    )
    deadline = models.ForeignKey(
        ClientDeadline, on_delete=models.RESTRICT, related_name="documents", null=True
    )
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to="client_documents/")
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, null=True, related_name="documents_uploaded"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.deadline} - {self.name}"

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Client Document"
        verbose_name_plural = "Client Documents"


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
