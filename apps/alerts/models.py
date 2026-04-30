# apps/alerts/models.py
import uuid
from django.db import models
from django.conf import settings


class Alert(models.Model):
    CHANNEL_CHOICES = [
        ("telegram",  "Telegram"),
        ("email",     "Email"),
        ("whatsapp",  "WhatsApp"),
        ("sms",       "SMS"),
    ]
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("sent",    "Envoyée"),
        ("failed",  "Échouée"),
        ("skipped", "Ignorée"),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    request     = models.ForeignKey("monitoring.VisaRequest", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="alerts")
    slot        = models.ForeignKey("monitoring.AppointmentSlot", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="alerts")
    channel     = models.CharField(max_length=15, choices=CHANNEL_CHOICES)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    message     = models.TextField()
    sent_at     = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.SmallIntegerField(default=0)
    max_retries = models.SmallIntegerField(default=3)
    scheduled_at = models.DateTimeField(auto_now_add=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.channel}] {self.user.email} – {self.status}"


class NotificationPreference(models.Model):
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                            related_name="notificationpreference")
    telegram_enabled  = models.BooleanField(default=True)
    email_enabled     = models.BooleanField(default=True)
    whatsapp_enabled  = models.BooleanField(default=False)
    sms_enabled       = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end   = models.TimeField(null=True, blank=True)
    max_alerts_per_day = models.SmallIntegerField(default=20)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Préférences notif – {self.user.email}"


# ─────────────────────────────────────────────────────────────
# apps/alerts/serializers.py
# ─────────────────────────────────────────────────────────────

from rest_framework import serializers


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Alert
        fields = ["id", "channel", "status", "message", "sent_at", "created_at"]


class NotifPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationPreference
        fields = ["telegram_enabled", "email_enabled", "whatsapp_enabled",
                  "sms_enabled", "quiet_hours_start", "quiet_hours_end", "max_alerts_per_day"]


# ─────────────────────────────────────────────────────────────
# apps/alerts/views.py
# ─────────────────────────────────────────────────────────────

from rest_framework import generics, permissions
from rest_framework.response import Response


class AlertListView(generics.ListAPIView):
    serializer_class   = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by("-created_at")[:50]


class NotifPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class   = NotifPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj
