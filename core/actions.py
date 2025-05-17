from core.models import AppLog, Notification


def create_log(user, details):
    AppLog.objects.create(user=user, details=details)


def create_notifications(recipient, title, message, link):
    Notification.objects.create(
        recipient=recipient, title=title, message=message, link=link
    )
