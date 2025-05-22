from core.models import AppLog, ClientDeadline, Notification
from core.utils import get_today_local


def create_log(user, details):
    AppLog.objects.create(user=user, details=details)


def create_notifications(recipient, title, message, link):
    Notification.objects.create(
        recipient=recipient, title=title, message=message, link=link
    )


def send_notification_on_reminder_date():
    today = get_today_local()
    for deadline in ClientDeadline.objects.filter(reminder_date=today):
        create_notifications(
            recipient=deadline.assigned_to,
            title="Upcoming Deadline Reminder",
            message=f"Friendly reminder: The deadline '{deadline}' is approaching. Please review your task.",
            link=f"/deadlines/{deadline.id}",
        )


def send_notification_for_due_tasks():
    today = get_today_local()
    for deadline in ClientDeadline.objects.filter(due_date=today):
        create_notifications(
            recipient=deadline.assigned_to,
            title="Action Required: Deadline Due Today",
            message=f"Urgent: The deadline '{deadline}' is due today. Please complete and submit as soon as possible.",
            link=f"/deadlines/{deadline.id}",
        )
