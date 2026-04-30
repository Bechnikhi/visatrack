# config/celery.py
"""
Configuration Celery pour VisaTrack.
Lancer les workers :
  celery -A config worker -l info -Q monitoring,alerts,default -c 4
  celery -A config beat   -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("visatrack")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# ──────────────────────────────────────────────
# QUEUES
# ──────────────────────────────────────────────
app.conf.task_queues = {
    "monitoring": {"exchange": "monitoring", "routing_key": "monitoring"},
    "alerts":     {"exchange": "alerts",     "routing_key": "alerts"},
    "billing":    {"exchange": "billing",    "routing_key": "billing"},
    "default":    {"exchange": "default",    "routing_key": "default"},
}
app.conf.task_default_queue = "default"

app.conf.task_routes = {
    "monitoring.*": {"queue": "monitoring"},
    "alerts.*":     {"queue": "alerts"},
    "billing.*":    {"queue": "billing"},
}


# ──────────────────────────────────────────────
# BEAT SCHEDULE — tâches planifiées
# ──────────────────────────────────────────────
app.conf.beat_schedule = {
    # Vérification des centres toutes les 60 secondes
    "check-all-centers": {
        "task": "monitoring.check_all_centers",
        "schedule": 60.0,
        "options": {"queue": "monitoring"},
    },
    # Nettoyage de nuit à 02:00
    "cleanup-old-slots": {
        "task": "monitoring.cleanup_old_slots",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "default"},
    },
    # Relances d'alertes échouées toutes les 5 min
    "retry-failed-alerts": {
        "task": "alerts.retry_failed",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "alerts"},
    },
    # Vérification expirations d'abonnements à 08:00
    "check-subscriptions": {
        "task": "billing.check_expiring_subscriptions",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "billing"},
    },
}

app.conf.timezone = "Africa/Dakar"
app.conf.task_serializer     = "json"
app.conf.result_serializer   = "json"
app.conf.accept_content      = ["json"]
app.conf.task_compression    = "gzip"
app.conf.worker_prefetch_multiplier = 1  # important pour les tâches longues


# ══════════════════════════════════════════════
# config/settings.py  (extraits pertinents)
# ══════════════════════════════════════════════

SETTINGS_SNIPPET = """
# ─── Redis / Celery ───────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CELERY_BROKER_URL  = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Cache Django (pour les tokens Telegram, rate limiting…)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

# ─── Email ────────────────────────────────────
EMAIL_BACKEND    = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST       = env("EMAIL_HOST",     default="smtp.gmail.com")
EMAIL_PORT       = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS    = True
EMAIL_HOST_USER  = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = "VisaTrack <alertes@visatrack.app>"

# ─── Telegram ────────────────────────────────
TELEGRAM_BOT_TOKEN      = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL    = env("TELEGRAM_WEBHOOK_URL")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET")

# ─── WhatsApp Business API ────────────────────
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_ID     = env("WHATSAPP_PHONE_ID")

# ─── Stripe ──────────────────────────────────
STRIPE_SECRET_KEY      = env("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET  = env("STRIPE_WEBHOOK_SECRET")

# ─── Monitoring ──────────────────────────────
MONITORING_REQUEST_TIMEOUT = 20     # secondes
MONITORING_MAX_RETRIES     = 3
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (compatible; VisaTrack/1.0; +https://visatrack.app)"
)

SITE_URL = env("SITE_URL", default="https://visatrack.app")

# ─── Applications Django ─────────────────────
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
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    # VisaTrack apps
    "apps.users",
    "apps.monitoring",
    "apps.alerts",
    "apps.billing",
    "apps.bot",
]
"""
