from core.models import AppLog, ClientDeadline, Notification
from core.utils import get_today_local


def create_log(user, details):
    """Create a new log entry in the application log.

    Args:
        user (User): The user associated with the log entry
        details (str): Description of the logged event
    """
    AppLog.objects.create(user=user, details=details)


def create_notifications(recipient, title, message, link):
    """Create a new notification for a user.

    Args:
        recipient (User): The user who will receive the notification
        title (str): Notification title/heading
        message (str): Detailed notification message
        link (str): URL link for the notification action
    """
    Notification.objects.create(
        recipient=recipient, title=title, message=message, link=link
    )


def send_notification_on_reminder_date():
    """Send notifications for deadlines where today is the reminder date.

    Creates notifications for all users who have deadlines with reminder dates
    matching today's date.
    """
    today = get_today_local()
    for deadline in ClientDeadline.objects.filter(reminder_date=today):
        create_notifications(
            recipient=deadline.assigned_to,
            title="Upcoming Deadline Reminder",
            message=f"Friendly reminder: The deadline '{deadline}' is approaching. Please review your task.",
            link=f"/deadlines/{deadline.id}",
        )


def send_notification_for_due_tasks():
    """Send notifications for deadlines that are due today.

    Creates urgent notifications for all users who have deadlines with due dates
    matching today's date.
    """
    today = get_today_local()
    for deadline in ClientDeadline.objects.filter(due_date=today):
        create_notifications(
            recipient=deadline.assigned_to,
            title="Action Required: Deadline Due Today",
            message=f"Urgent: The deadline '{deadline}' is due today. Please complete and submit as soon as possible.",
            link=f"/deadlines/{deadline.id}",
        )


def update_deadline_statuses():
    """Automatically update deadline statuses based on due dates and send notifications."""
    today = get_today_local()

    pending_to_overdue = ClientDeadline.objects.filter(
        due_date__lt=today, status="pending"
    ).select_related("assigned_to")

    overdue_to_pending = ClientDeadline.objects.filter(
        due_date__gt=today, status="overdue"
    ).select_related("assigned_to")

    updates = []
    for deadline in pending_to_overdue:
        deadline.status = "overdue"
        updates.append(deadline)

    for deadline in overdue_to_pending:
        deadline.status = "pending"
        updates.append(deadline)

    if updates:
        ClientDeadline.objects.bulk_update(updates, ["status"])

        # Send notifications
        for deadline in pending_to_overdue:
            create_notifications(
                recipient=deadline.assigned_to,
                title="Deadline Status Updated",
                message=f"The deadline '{deadline.title}' (due {deadline.due_date}) has been marked as Overdue.",
                link=f"/deadlines/{deadline.id}",
            )

        for deadline in overdue_to_pending:
            create_notifications(
                recipient=deadline.assigned_to,
                title="Deadline Status Updated",
                message=f"The deadline '{deadline.title}' (due {deadline.due_date}) has been reverted to Pending status.",
                link=f"/deadlines/{deadline.id}",
            )
