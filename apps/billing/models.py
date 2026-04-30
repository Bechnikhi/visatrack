# apps/billing/models.py
import uuid
from django.db import models
from django.conf import settings


class Subscription(models.Model):
    PLAN_CHOICES   = [("free","Gratuit"),("premium","Premium"),("vip","VIP")]
    STATUS_CHOICES = [("active","Actif"),("cancelled","Annulé"),("expired","Expiré"),("trial","Essai")]
    BILLING_CHOICES = [("monthly","Mensuel"),("yearly","Annuel")]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan           = models.CharField(max_length=10, choices=PLAN_CHOICES)
    status         = models.CharField(max_length=15, choices=STATUS_CHOICES, default="active")
    price_fcfa     = models.IntegerField()
    billing_period = models.CharField(max_length=20, choices=BILLING_CHOICES, default="monthly")
    started_at     = models.DateTimeField(auto_now_add=True)
    expires_at     = models.DateTimeField()
    cancelled_at   = models.DateTimeField(null=True, blank=True)
    auto_renew     = models.BooleanField(default=True)
    stripe_sub_id  = models.CharField(max_length=100, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} – {self.plan} [{self.status}]"


class Invoice(models.Model):
    STATUS_CHOICES = [("draft","Brouillon"),("sent","Envoyée"),("paid","Payée"),
                      ("overdue","En retard"),("cancelled","Annulée")]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoices")
    subscription    = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL)
    invoice_number  = models.CharField(max_length=30, unique=True, blank=True)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    amount_fcfa     = models.IntegerField()
    tax_fcfa        = models.IntegerField(default=0)
    total_fcfa      = models.IntegerField()
    description     = models.TextField(blank=True)
    due_date        = models.DateField()
    paid_at         = models.DateTimeField(null=True, blank=True)
    pdf_path        = models.CharField(max_length=255, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            from django.utils import timezone
            import random
            year = timezone.now().year
            num  = random.randint(100000, 999999)
            self.invoice_number = f"VT-{year}-{num}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} – {self.user.email} – {self.total_fcfa} FCFA"


class Payment(models.Model):
    METHOD_CHOICES = [("stripe","Stripe"),("wave","Wave"),("orange_money","Orange Money"),
                      ("free_mobile","Free Mobile"),("mtn","MTN"),("manual","Manuel")]
    STATUS_CHOICES = [("pending","En attente"),("paid","Payé"),("failed","Échoué"),
                      ("refunded","Remboursé"),("disputed","Litige")]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice     = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    method      = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    amount_fcfa = models.IntegerField()
    currency    = models.CharField(max_length=3, default="XOF")
    gateway_ref = models.CharField(max_length=150, blank=True)
    gateway_data = models.JSONField(default=dict, blank=True)
    paid_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method} – {self.amount_fcfa} FCFA [{self.status}]"


# ─────────────────────────────────────────────────────────────
# apps/billing/views.py
# ─────────────────────────────────────────────────────────────

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import stripe, os
from django.conf import settings as django_settings
from .models import Subscription, Invoice


class SubscriptionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subs = Subscription.objects.filter(user=request.user).order_by("-created_at")
        data = [{
            "id": str(s.id), "plan": s.plan, "status": s.status,
            "price_fcfa": s.price_fcfa, "billing_period": s.billing_period,
            "expires_at": s.expires_at, "auto_renew": s.auto_renew,
        } for s in subs]
        return Response(data)


class InvoiceListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        invoices = Invoice.objects.filter(user=request.user).order_by("-created_at")
        data = [{
            "id": str(i.id), "invoice_number": i.invoice_number,
            "status": i.status, "total_fcfa": i.total_fcfa,
            "due_date": i.due_date, "paid_at": i.paid_at,
        } for i in invoices]
        return Response(data)


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    PLANS = {
        "premium": {"price_fcfa": 9900,  "stripe_price": os.environ.get("STRIPE_PRICE_PREMIUM", "")},
        "vip":     {"price_fcfa": 24900, "stripe_price": os.environ.get("STRIPE_PRICE_VIP", "")},
    }

    def post(self, request):
        plan = request.data.get("plan")
        if plan not in self.PLANS:
            return Response({"error": "Plan invalide."}, status=400)

        stripe.api_key = django_settings.STRIPE_SECRET_KEY
        plan_data = self.PLANS[plan]

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": plan_data["stripe_price"], "quantity": 1}],
                mode="subscription",
                success_url=f"{django_settings.SITE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{django_settings.SITE_URL}/billing/cancel",
                metadata={"user_id": str(request.user.id), "plan": plan},
                customer_email=request.user.email,
            )
            return Response({"checkout_url": session.url, "session_id": session.id})
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload    = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        stripe.api_key = django_settings.STRIPE_SECRET_KEY

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, django_settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=400)

        if event["type"] == "checkout.session.completed":
            self._handle_checkout_completed(event["data"]["object"])
        elif event["type"] == "customer.subscription.deleted":
            self._handle_subscription_cancelled(event["data"]["object"])

        return Response({"received": True})

    def _handle_checkout_completed(self, session):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        User = get_user_model()

        user_id = session.get("metadata", {}).get("user_id")
        plan    = session.get("metadata", {}).get("plan", "premium")
        user    = User.objects.filter(id=user_id).first()
        if not user:
            return

        expires = timezone.now() + timezone.timedelta(days=30)
        user.plan        = plan
        user.plan_status = "active"
        user.plan_expires_at = expires
        user.save(update_fields=["plan", "plan_status", "plan_expires_at"])

        Subscription.objects.create(
            user=user, plan=plan, status="active",
            price_fcfa=9900 if plan == "premium" else 24900,
            expires_at=expires,
            stripe_sub_id=session.get("subscription", ""),
        )

    def _handle_subscription_cancelled(self, subscription):
        Subscription.objects.filter(
            stripe_sub_id=subscription["id"]
        ).update(status="cancelled")
