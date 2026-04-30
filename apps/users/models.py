# apps/users/models.py
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role",       "superadmin")
        extra_fields.setdefault("is_staff",   True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("client",     "Client"),
        ("agent",      "Agent"),
        ("admin",      "Administrateur"),
        ("superadmin", "Super Administrateur"),
    ]
    PLAN_CHOICES = [
        ("free",    "Gratuit"),
        ("premium", "Premium"),
        ("vip",     "VIP"),
    ]
    PLAN_STATUS_CHOICES = [
        ("active",    "Actif"),
        ("cancelled", "Annulé"),
        ("expired",   "Expiré"),
        ("trial",     "Essai"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email           = models.EmailField(unique=True)
    full_name       = models.CharField(max_length=120)
    phone           = models.CharField(max_length=30, blank=True)
    role            = models.CharField(max_length=20, choices=ROLE_CHOICES, default="client")
    plan            = models.CharField(max_length=10, choices=PLAN_CHOICES,  default="free")
    plan_status     = models.CharField(max_length=15, choices=PLAN_STATUS_CHOICES, default="active")
    plan_expires_at = models.DateTimeField(null=True, blank=True)

    telegram_chat_id = models.BigIntegerField(null=True, blank=True, unique=True)
    whatsapp_number  = models.CharField(max_length=30, blank=True)

    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    otp_code       = models.CharField(max_length=8, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)

    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name        = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}> [{self.plan.upper()}]"

    @property
    def is_premium_or_vip(self):
        return self.plan in ("premium", "vip") and self.plan_status == "active"

    def generate_otp(self):
        import random, string
        from django.utils import timezone
        self.otp_code       = "".join(random.choices(string.digits, k=6))
        self.otp_expires_at = timezone.now() + timezone.timedelta(minutes=10)
        self.save(update_fields=["otp_code", "otp_expires_at"])
        return self.otp_code
