from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("staff", "Staff"),
    ]

    middle_name = models.CharField(_("Middle Name"), max_length=150, blank=True)
    role = models.CharField(
        max_length=5,
        choices=ROLE_CHOICES,
        default="staff",
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


class Client(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
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
        (1, "Lowest"),
        (2, "Low"),
        (3, "Medium"),
        (4, "High"),
        (5, "Highest"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
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

        # Auto-update status if due_date is in the past and status is pending
        if self.due_date < timezone.now().date() and self.status == "pending":
            self.status = "overdue"
        elif self.due_date > timezone.now().date() and self.status == "overdue":
            self.status = "pending"

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["due_date", "-priority"]
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
        return f"{self.client.name} - {self.name}"

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Client Document"
        verbose_name_plural = "Client Documents"
