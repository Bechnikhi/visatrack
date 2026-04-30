"""
VisaTrack — Configuration Django complète
"""

import os
from pathlib import Path
from datetime import timedelta
import environ

# ── Chemins ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Variables d'environnement ────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

# ── Sécurité ────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-in-production-!!!")
DEBUG      = env("DEBUG", default=True)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

SITE_URL = env("SITE_URL", default="http://localhost:8000")

# ── Applications ─────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "django_filters",
    "drf_spectacular",
    # VisaTrack
    "apps.users",
    "apps.monitoring",
    "apps.alerts",
    "apps.billing",
    "apps.bot",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# ── Base de données ──────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = 60

# ── Auth personnalisé ────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ─────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
TIME_ZONE     = "Africa/Dakar"
USE_I18N      = True
USE_TZ        = True

# ── Fichiers statiques ───────────────────────────────────────
STATIC_URL   = "/static/"
STATIC_ROOT  = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Django REST Framework ────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "200/minute",
    },
}

# ── JWT ──────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES":      ("Bearer",),
    "UPDATE_LAST_LOGIN":      True,
}

# ── CORS ─────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_CREDENTIALS = True

# ── Redis / Celery ───────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CELERY_BROKER_URL             = REDIS_URL
CELERY_RESULT_BACKEND         = "django-db"
CELERY_CACHE_BACKEND          = "django-cache"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_ACCEPT_CONTENT         = ["json"]
CELERY_TASK_SERIALIZER        = "json"
CELERY_RESULT_SERIALIZER      = "json"
CELERY_TIMEZONE               = "Africa/Dakar"
CELERY_BEAT_SCHEDULER         = "django_celery_beat.schedulers:DatabaseScheduler"

CACHES = {
    "default": {
        "BACKEND":  "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS":          "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT":         5,
            "IGNORE_EXCEPTIONS":      True,
        },
        "KEY_PREFIX": "visatrack",
    }
}

# ── Email ────────────────────────────────────────────────────
EMAIL_BACKEND       = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST          = env("EMAIL_HOST",     default="smtp.gmail.com")
EMAIL_PORT          = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = env("EMAIL_HOST_USER",     default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL",  default="VisaTrack <noreply@visatrack.app>")
SERVER_EMAIL        = DEFAULT_FROM_EMAIL

# ── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN       = env("TELEGRAM_BOT_TOKEN",       default="")
TELEGRAM_WEBHOOK_URL     = env("TELEGRAM_WEBHOOK_URL",     default="")
TELEGRAM_WEBHOOK_SECRET  = env("TELEGRAM_WEBHOOK_SECRET",  default="changeme")

# ── WhatsApp Business API ────────────────────────────────────
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_PHONE_ID     = env("WHATSAPP_PHONE_ID",     default="")

# ── Stripe ───────────────────────────────────────────────────
STRIPE_SECRET_KEY      = env("STRIPE_SECRET_KEY",      default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET  = env("STRIPE_WEBHOOK_SECRET",  default="")

# ── Paramètres monitoring ────────────────────────────────────
MONITORING_REQUEST_TIMEOUT = 20
MONITORING_MAX_RETRIES     = 3
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
)

# ── API Docs ─────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE":       "VisaTrack API",
    "DESCRIPTION": "API de la plateforme SaaS de surveillance de créneaux visa",
    "VERSION":     "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ── Logging ──────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class":     "logging.handlers.RotatingFileHandler",
            "filename":  BASE_DIR / "logs" / "visatrack.log",
            "maxBytes":  10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps.monitoring": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "apps.alerts":     {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "django":          {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
