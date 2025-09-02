from celery import shared_task

from core.actions import (
    send_client_birthday_notifications,
    send_notification_for_due_tasks,
    send_notification_on_reminder_date,
)


@shared_task
def daily_notification_reminder():
    send_notification_on_reminder_date()
    send_notification_for_due_tasks()
    send_client_birthday_notifications()
