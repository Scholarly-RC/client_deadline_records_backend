from django.db import models


class TaskStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    FOR_REVISION = "for_revision", "For Revision"
    FOR_CHECKING = "for_checking", "For Checking"
    ON_GOING = "on_going", "On Going"
    PENDING = "pending", "Pending"
    NOT_YET_STARTED = "not_yet_started", "Not Yet Started"
    CANCELLED = "cancelled", "Cancelled"


class TaskPriority(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class ClientStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class UserRoles(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
