from django.contrib import admin
from .models import Country, VisaCenter, VisaRequest, AppointmentSlot, MonitoringLog


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display  = ["flag_emoji", "code", "name_fr", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["name_fr", "code"]


@admin.register(VisaCenter)
class VisaCenterAdmin(admin.ModelAdmin):
    list_display  = ["platform", "country", "city", "check_interval", "is_active", "last_checked_at"]
    list_filter   = ["platform", "is_active"]
    list_editable = ["check_interval", "is_active"]
    search_fields = ["city", "country__name_fr"]


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(admin.ModelAdmin):
    list_display  = ["center", "slot_date", "slot_time", "available_seats", "status", "first_seen_at"]
    list_filter   = ["status", "center__platform"]
    search_fields = ["center__city"]


@admin.register(VisaRequest)
class VisaRequestAdmin(admin.ModelAdmin):
    list_display    = ["user", "center", "status", "priority", "desired_date_from", "created_at"]
    list_filter     = ["status", "priority", "center__platform"]
    search_fields   = ["user__email", "applicant_name"]
    readonly_fields = ["created_at", "updated_at", "slot_found_at"]


@admin.register(MonitoringLog)
class MonitoringLogAdmin(admin.ModelAdmin):
    list_display = ["center", "checked_at", "duration_ms", "slots_found", "slots_new", "success"]
    list_filter  = ["success", "center"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False