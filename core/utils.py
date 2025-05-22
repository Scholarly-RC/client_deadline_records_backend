from django.contrib.auth import get_user_model
from django.utils import timezone


def get_admin_users():
    """
    Get Users withs admin role.
    """
    return get_user_model().objects.filter(role="admin", is_superuser=False)


def get_notification_recipients(deadline):
    """ """
    users = [user for user in get_admin_users()]
    if deadline.assigned_to:
        users.append(deadline.assigned_to)
    return users


def get_now_local():
    """Returns current local time (timezone-aware)."""
    return timezone.localtime(timezone.now())


def get_today_local():
    """Returns today's date in local time."""
    return get_now_local().date()
