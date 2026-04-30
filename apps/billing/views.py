from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings as django_settings
from .models import Subscription, Invoice
import os, stripe

class SubscriptionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        subs = Subscription.objects.filter(user=request.user).order_by("-created_at")
        data = [{"id": str(s.id), "plan": s.plan, "status": s.status,
                 "price_fcfa": s.price_fcfa, "expires_at": s.expires_at} for s in subs]
        return Response(data)

class InvoiceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        invoices = Invoice.objects.filter(user=request.user).order_by("-created_at")
        data = [{"id": str(i.id), "invoice_number": i.invoice_number,
                 "status": i.status, "total_fcfa": i.total_fcfa} for i in invoices]
        return Response(data)

class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        return Response({"message": "Stripe checkout — configurez STRIPE_SECRET_KEY dans .env"})

@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        return Response({"received": True})
