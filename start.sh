#!/bin/bash
set -e

# Run Celery worker in background (with --uid to avoid root warning if running as root)
celery -A client_deadline_records_backend worker --loglevel=info --uid=1000 --gid=1000 2>&1 | sed 's/SecurityWarning.*//' || celery -A client_deadline_records_backend worker --loglevel=info &
WORKER_PID=$!

# Run Celery beat in background (with --uid to avoid root warning if running as root)
celery -A client_deadline_records_backend beat --loglevel=info --uid=1000 --gid=1000 2>&1 | sed 's/SecurityWarning.*//' || celery -A client_deadline_records_backend beat --loglevel=info &
BEAT_PID=$!

# Wait a moment for Celery to start
sleep 2

# Run migrations and collectstatic
python manage.py migrate
python manage.py collectstatic --noinput

# Start gunicorn (foreground process)
gunicorn client_deadline_records_backend.wsgi

# Wait for background processes (shouldn't reach here as gunicorn runs forever)
wait $WORKER_PID $BEAT_PID

