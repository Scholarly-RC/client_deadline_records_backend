web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn client_deadline_records_backend.wsgi
worker: celery -A client_deadline_records_backend worker --loglevel=info
beat: celery -A client_deadline_records_backend beat --loglevel=info