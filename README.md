# Client Deadline Records Backend

# This is the backend system for Client Deadline Records,

# built with Django and powered by Celery for background task management.

# ---------------------------------------

# 🛠️ Requirements

# ---------------------------------------

# - Python 3.8+

# - Django 4.x+

# - Redis (as Celery broker)

# - PostgreSQL or SQLite (for development)

# ---------------------------------------

# 📦 Installation

# ---------------------------------------

# 1. Clone the repository

git clone https://github.com/your-username/client_deadline_records_backend.git
cd client_deadline_records_backend

# 2. Create and activate virtual environment

python -m venv env
source env/bin/activate # On Windows: env\Scripts\activate

# 3. Install dependencies

pip install -r requirements.txt

# 4. Set up environment variables

# 5. Apply database migrations

python manage.py migrate

# 6. (Optional) Create a superuser

python manage.py createsuperuser

# ---------------------------------------

# 💻 Running the Project

# ---------------------------------------

# Start Django server

python manage.py runserver

# In another terminal, start Celery worker

celery -A client_deadline_records_backend worker --loglevel=info

# In another terminal, start Celery Beat scheduler

celery -A client_deadline_records_backend beat --loglevel=info
