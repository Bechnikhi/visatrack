from rest_framework import serializers
from .models import Alert, NotificationPreference

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Alert
        fields = ["id", "channel", "status", "message", "sent_at", "created_at"]

class NotifPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationPreference
        fields = ["telegram_enabled", "email_enabled", "whatsapp_enabled",
                  "sms_enabled", "quiet_hours_start", "quiet_hours_end", "max_alerts_per_day"]
