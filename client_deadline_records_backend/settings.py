import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# Function to detect if we're running tests
def is_running_tests():
    """Check if Django is running tests"""
    # Check for Django test runner
    if "test" in sys.argv and len(sys.argv) > 1:
        return True

    # Check for pytest
    if "pytest" in sys.argv[0] if sys.argv else False:
        return True

    # Check for Django's test settings module
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if "test" in settings_module:
        return True

    # Check for specific test-related environment variables
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get(
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD"
    ):
        return True

    return False


SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG", False) == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")

CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api",
    "core",
    "corsheaders",
    "django_celery_beat",
    "django_filters",
    "rest_framework",
    "drf_spectacular",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "client_deadline_records_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "client_deadline_records_backend.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Manila"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = os.path.join(BASE_DIR, "uploads")
MEDIA_URL = "/uploads/"

# Cloudflare R2 Storage Configuration
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_REGION_NAME = os.getenv("R2_REGION_NAME", "auto")

# Storage Configuration with Test Detection
# NEVER use R2 during testing - always use local storage for tests
if is_running_tests():
    # Force local storage during tests
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    print("🧪 TEST MODE: Using local file storage (R2 disabled for testing)")
elif os.getenv("USE_R2_STORAGE", "False").lower() == "true" and all(
    [R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_ENDPOINT_URL]
):
    # Production: Use Cloudflare R2
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_REGION_NAME = R2_REGION_NAME
    AWS_S3_CUSTOM_DOMAIN = None
    AWS_DEFAULT_ACL = "public-read"
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }

    # Use S3 storage for client documents
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    # Force the storage to be properly initialized
    import django.core.files.storage
    from storages.backends.s3boto3 import S3Boto3Storage

    django.core.files.storage.default_storage = S3Boto3Storage()

    print("☁️ PRODUCTION MODE: Using Cloudflare R2 storage")
else:
    # Development: Use default Django storage
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    print("💻 DEVELOPMENT MODE: Using local file storage")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Client Deadline Records Backend API",
    "DESCRIPTION": "Backend system for managing client deadlines and task tracking",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "TaskStatusEnum": "core.choices.TaskStatus",
        "ClientStatusEnum": "core.choices.ClientStatus",
        "TaskCategoryEnum": "core.choices.TaskCategory",
        "TaskPriorityEnum": "core.choices.TaskPriority",
        "UserRoleEnum": "core.choices.UserRoles",
        "TaxCaseCategoryEnum": "core.choices.TaxCaseCategory",
        "TypeOfTaxCaseEnum": "core.choices.TypeOfTaxCase",
        "BirFormsEnum": "core.choices.BirForms",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

FRONTEND_URL = os.getenv("FRONTEND_URL", "localhost:3000")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"


CELERY_BEAT_SCHEDULE = {
    "send-deadline-notifications": {
        "task": "core.tasks.daily_notification_reminder",
        "schedule": crontab(minute=0, hour=6),
    },
}
