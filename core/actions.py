from core.models import AppLog


def create_log(user, details):
    AppLog.objects.create(user=user, details=details)
