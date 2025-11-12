"""
Django settings for whatsapp_sender project.
"""

import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url  # Optional if you move to PostgreSQL later

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# SECURITY & DEBUG
# ---------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=Csv()
)

# ---------------------------------------------------------------------
# INSTALLED APPS
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",  # For AWS S3 storage
    "messaging",
    "messaging2",
]

# ---------------------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "whatsapp_sender.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "whatsapp_sender.wsgi.application"

# ---------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ---------------------------------------------------------------------
# PASSWORD VALIDATION
# ---------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------
# LANGUAGE, TIMEZONE
# ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------
# AWS S3 STORAGE SETTINGS
# ---------------------------------------------------------------------
USE_S3 = config("USE_S3", default=False, cast=bool)

if USE_S3:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    STATIC_LOCATION = "static"
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    MEDIA_LOCATION = "media"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/"
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
else:
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.join(BASE_DIR, "static")

    MEDIA_URL = "/media/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# ---------------------------------------------------------------------
# DEFAULT PRIMARY KEY FIELD
# ---------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------
# WHATSAPP API CREDENTIALS
# ---------------------------------------------------------------------
WHATSAPP_ACCESS_TOKEN = config("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_BUSINESS_ACCOUNT_ID = config("WHATSAPP_BUSINESS_ACCOUNT_ID")
WHATSAPP_VERIFY_TOKEN = config("WHATSAPP_VERIFY_TOKEN")

WHATSAPP2_ACCESS_TOKEN = config("WHATSAPP2_ACCESS_TOKEN")
WHATSAPP2_PHONE_NUMBER_ID = config("WHATSAPP2_PHONE_NUMBER_ID")
WHATSAPP2_BUSINESS_ACCOUNT_ID = config("WHATSAPP2_BUSINESS_ACCOUNT_ID")
WHATSAPP2_VERIFY_TOKEN = config("WHATSAPP2_VERIFY_TOKEN")

# ---------------------------------------------------------------------
# CELERY + REDIS CONFIG
# ---------------------------------------------------------------------
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_TASK_ROUTES = {
    "messaging.tasks.*": {"queue": "whatsapp_main"},
    "messaging2.tasks.*": {"queue": "whatsapp_secondary"},
}

# ---------------------------------------------------------------------
# CSRF / NGROK
# ---------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [
    "https://lavone-prerestoration-aydan.ngrok-free.dev",
    "https://ec2-52-221-199-190.ap-southeast-1.compute.amazonaws.com",
]

# ---------------------------------------------------------------------
# FILE UPLOAD DIRECTORIES
# ---------------------------------------------------------------------
UPLOAD_DIR_1 = os.path.join(BASE_DIR, "uploads")
UPLOAD_DIR_2 = os.path.join(BASE_DIR, "uploads2")
os.makedirs(UPLOAD_DIR_1, exist_ok=True)
os.makedirs(UPLOAD_DIR_2, exist_ok=True)

# ---------------------------------------------------------------------
# SECURITY HEADERS
# ---------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
