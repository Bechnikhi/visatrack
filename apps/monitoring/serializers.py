# apps/monitoring/serializers.py
from rest_framework import serializers
from .models import Country, VisaCenter, VisaType, VisaRequest, AppointmentSlot, MonitoringLog


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Country
        fields = ["id", "code", "name_fr", "flag_emoji"]


class VisaCenterSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)

    class Meta:
        model  = VisaCenter
        fields = ["id", "platform", "country", "city", "url_booking",
                  "check_interval", "is_active", "last_checked_at"]


class SlotSerializer(serializers.ModelSerializer):
    center = VisaCenterSerializer(read_only=True)

    class Meta:
        model  = AppointmentSlot
        fields = ["id", "center", "slot_date", "slot_time",
                  "available_seats", "status", "first_seen_at"]


class VisaRequestSerializer(serializers.ModelSerializer):
    center_detail = VisaCenterSerializer(source="center", read_only=True)

    class Meta:
        model  = VisaRequest
        fields = [
            "id", "center", "center_detail", "visa_type", "status", "priority",
            "desired_date_from", "desired_date_to", "preferred_time_from", "preferred_time_to",
            "num_applicants", "applicant_name", "notes",
            "slot_found_at", "booked_at", "appointment_date", "appointment_time",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "slot_found_at", "booked_at",
                            "appointment_date", "appointment_time", "created_at", "updated_at"]


class MonitoringLogSerializer(serializers.ModelSerializer):
    center_name = serializers.StringRelatedField(source="center")

    class Meta:
        model  = MonitoringLog
        fields = ["id", "center", "center_name", "checked_at", "duration_ms",
                  "slots_found", "slots_new", "http_status", "error_message", "success"]
