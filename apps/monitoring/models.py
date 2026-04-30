# apps/monitoring/models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Country(models.Model):
    code     = models.CharField(max_length=2, unique=True)
    name_fr  = models.CharField(max_length=80)
    name_en  = models.CharField(max_length=80)
    flag_emoji = models.CharField(max_length=10, blank=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "countries"
        ordering = ["name_fr"]

    def __str__(self):
        return f"{self.flag_emoji} {self.name_fr}"


class VisaCenter(models.Model):
    PLATFORM_CHOICES = [("BLS", "BLS International"), ("TLScontact", "TLScontact"), ("VFS", "VFS Global")]

    platform        = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    country         = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="centers")
    city            = models.CharField(max_length=80)
    address         = models.TextField(blank=True)
    url_booking     = models.URLField()
    url_check       = models.URLField(blank=True)
    check_interval  = models.SmallIntegerField(default=5, help_text="Minutes entre chaque vérification")
    is_active       = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("platform", "country", "city")]
        ordering = ["platform", "country__name_fr"]

    def __str__(self):
        return f"{self.platform} – {self.city} ({self.country.code})"


class VisaType(models.Model):
    country   = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="visa_types")
    code      = models.CharField(max_length=30)
    label_fr  = models.CharField(max_length=100)
    duration  = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("country", "code")]

    def __str__(self):
        return f"{self.label_fr} – {self.country.code}"


class VisaRequest(models.Model):
    STATUS_CHOICES = [
        ("draft",      "Brouillon"),
        ("active",     "Surveillance active"),
        ("slot_found", "Créneau trouvé"),
        ("booked",     "Réservé"),
        ("completed",  "Terminé"),
        ("cancelled",  "Annulé"),
        ("expired",    "Expiré"),
    ]
    PRIORITY_CHOICES = [
        ("low",    "Faible"),
        ("normal", "Normal"),
        ("high",   "Élevé"),
        ("urgent", "Urgent"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requests")
    center          = models.ForeignKey(VisaCenter, on_delete=models.PROTECT, related_name="requests")
    visa_type       = models.ForeignKey(VisaType, null=True, blank=True, on_delete=models.SET_NULL)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    priority        = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")

    desired_date_from   = models.DateField()
    desired_date_to     = models.DateField(null=True, blank=True)
    preferred_time_from = models.TimeField(null=True, blank=True)
    preferred_time_to   = models.TimeField(null=True, blank=True)
    num_applicants      = models.SmallIntegerField(default=1)

    applicant_name  = models.CharField(max_length=120, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    notes           = models.TextField(blank=True)

    slot_found_at    = models.DateTimeField(null=True, blank=True)
    booked_at        = models.DateTimeField(null=True, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    appointment_time = models.TimeField(null=True, blank=True)

    created_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_requests")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} → {self.center} [{self.status}]"


class AppointmentSlot(models.Model):
    STATUS_CHOICES = [("available", "Disponible"), ("taken", "Pris"), ("expired", "Expiré")]

    center          = models.ForeignKey(VisaCenter, on_delete=models.CASCADE, related_name="slots")
    visa_type       = models.ForeignKey(VisaType, null=True, blank=True, on_delete=models.SET_NULL)
    slot_date       = models.DateField()
    slot_time       = models.TimeField(null=True, blank=True)
    available_seats = models.SmallIntegerField(default=1)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default="available")
    raw_data        = models.JSONField(default=dict, blank=True)
    first_seen_at   = models.DateTimeField(auto_now_add=True)
    last_seen_at    = models.DateTimeField(auto_now=True)
    taken_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("center", "slot_date", "slot_time")]
        ordering = ["slot_date", "slot_time"]

    def __str__(self):
        t = self.slot_time.strftime("%H:%M") if self.slot_time else "–"
        return f"{self.center} | {self.slot_date} {t} [{self.status}]"


class MonitoringLog(models.Model):
    center       = models.ForeignKey(VisaCenter, on_delete=models.CASCADE, related_name="logs")
    checked_at   = models.DateTimeField(auto_now_add=True)
    duration_ms  = models.IntegerField(null=True, blank=True)
    slots_found  = models.SmallIntegerField(default=0)
    slots_new    = models.SmallIntegerField(default=0)
    http_status  = models.SmallIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    success      = models.BooleanField(default=True)

    class Meta:
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.center} @ {self.checked_at:%Y-%m-%d %H:%M} – {'OK' if self.success else 'ERR'}"
