from django.contrib import admin
from .models import Subscription, Invoice, Payment

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "price_fcfa", "expires_at"]
    list_filter  = ["plan", "status"]

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "user", "status", "total_fcfa", "due_date"]
    list_filter  = ["status"]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "method", "status", "amount_fcfa", "paid_at"]
    list_filter  = ["method", "status"]
