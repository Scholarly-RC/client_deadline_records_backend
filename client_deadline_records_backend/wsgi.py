import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "client_deadline_records_backend.settings"
)

application = get_wsgi_application()
