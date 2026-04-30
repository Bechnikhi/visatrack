from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ["email", "full_name", "plan", "role", "is_active", "created_at"]
    list_filter   = ["plan", "role", "is_active"]
    search_fields = ["email", "full_name"]
    ordering      = ["-created_at"]
    fieldsets = (
        ("Identité",      {"fields": ("email", "full_name", "phone", "password")}),
        ("Rôle & Plan",   {"fields": ("role", "plan", "plan_status", "plan_expires_at")}),
        ("Notifications", {"fields": ("telegram_chat_id", "whatsapp_number")}),
        ("Permissions",   {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),)
