#!/bin/bash
set -e

# Check if running as root
if [ "$(id -u)" = "0" ]; then
    # Running as root - try to find an existing non-root user
    # Look for any user with UID >= 1000 (typical non-root user range)
    NON_ROOT_USER=$(getent passwd 2>/dev/null | awk -F: '$3 >= 1000 && $3 != 65534 {print $1; exit}' || echo "")
    
    if [ -n "$NON_ROOT_USER" ]; then
        # Use existing non-root user
        CELERY_UID_OPT="--uid=$NON_ROOT_USER --gid=$NON_ROOT_USER"
        echo "Using non-root user: $NON_ROOT_USER"
    else
        # No non-root user found - Railway containers might not have one
        # Run without --uid (will show warning but is safe in containerized environments)
        CELERY_UID_OPT=""
        echo "Running as root (warning will appear but is safe in Railway containers)"
    fi
else
    # Already running as non-root, no need for --uid
    CELERY_UID_OPT=""
    echo "Running as non-root user: $(id -un)"
fi

# Run Celery worker in background
celery -A client_deadline_records_backend worker --loglevel=info $CELERY_UID_OPT &
WORKER_PID=$!

# Run Celery beat in background  
celery -A client_deadline_records_backend beat --loglevel=info $CELERY_UID_OPT &
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

