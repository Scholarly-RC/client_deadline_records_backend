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

# ---------------------------------------

# 📚 API Documentation

# ---------------------------------------

# The API documentation is automatically generated using DRF Spectacular.
# You can access the documentation in different formats:

# Swagger UI (interactive documentation):
# http://127.0.0.1:8000/api/schema/swagger-ui/

# Redoc (alternative documentation):
# http://127.0.0.1:8000/api/schema/redoc/

# Raw schema (YAML):
# http://127.0.0.1:8000/api/schema/

# To regenerate the schema file:

python manage.py generate_schema

# Or to generate with validation:

python manage.py spectacular --file schema.yml --validate
