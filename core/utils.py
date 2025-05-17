from core.models import User


def get_admin_users():
    """
    Get Users withs admin role.
    """
    return User.objects.filter(role="admin", is_superuser=False)


def get_notification_recipients(deadline):
    """ """
    users = [user for user in get_admin_users()]
    if deadline.assigned_to:
        users.append(deadline.assigned_to)
    return users
