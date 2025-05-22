from django.contrib.auth import get_user_model
from django.utils import timezone


def get_admin_users():
    """Return all admin users (non-superusers with admin role).

    Returns:
        QuerySet: A queryset of User objects filtered by admin role
    """
    return get_user_model().objects.filter(role="admin", is_superuser=False)


def get_notification_recipients(deadline):
    """Get all users who should be notified about a deadline.

    Args:
        deadline (ClientDeadline): The deadline instance to check

    Returns:
        list: List of User objects including admins and the assigned user (if any)
    """
    users = [user for user in get_admin_users()]
    if deadline.assigned_to:
        users.append(deadline.assigned_to)
    return users


def get_now_local():
    """Get the current time in local timezone.

    Returns:
        datetime: Timezone-aware datetime object in local time
    """
    return timezone.localtime(timezone.now())


def get_today_local():
    """Get today's date in local timezone.

    Returns:
        date: Date object representing today in local time
    """
    return get_now_local().date()
