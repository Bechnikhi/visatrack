from django.contrib import admin
from .models import Alert, NotificationPreference

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["user", "channel", "status", "sent_at", "created_at"]
    list_filter  = ["channel", "status"]

@admin.register(NotificationPreference)
class NotifPrefAdmin(admin.ModelAdmin):
    list_display = ["user", "telegram_enabled", "email_enabled", "whatsapp_enabled"]
