from django.urls import path
from .views import SubscriptionListView, InvoiceListView, CheckoutView, StripeWebhookView

urlpatterns = [
    path("subscriptions/",  SubscriptionListView.as_view(), name="subscriptions-list"),
    path("invoices/",       InvoiceListView.as_view(),      name="invoices-list"),
    path("checkout/",       CheckoutView.as_view(),          name="billing-checkout"),
    path("webhook/stripe/", StripeWebhookView.as_view(),    name="stripe-webhook"),
]
