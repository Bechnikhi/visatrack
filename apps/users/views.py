# apps/users/views.py
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
import uuid

from .serializers import RegisterSerializer, UserProfileSerializer, ChangePasswordSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — Inscription"""
    queryset         = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Envoyer OTP de vérification
        otp = user.generate_otp()
        # TODO: envoyer l'email de vérification
        tokens = _get_tokens(user)
        return Response({
            "message": "Compte créé. Vérifiez votre email.",
            "user":    UserProfileSerializer(user).data,
            **tokens,
        }, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/ — Profil utilisateur"""
    serializer_class   = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    """POST /api/auth/change-password/"""
    serializer_class   = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"message": "Mot de passe modifié."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/ — Révoque le refresh token"""
    try:
        token = RefreshToken(request.data["refresh"])
        token.blacklist()
    except Exception:
        pass
    return Response({"message": "Déconnecté."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def generate_telegram_link_token(request):
    """Génère un token temporaire pour lier Telegram."""
    token = str(uuid.uuid4()).replace("-", "")[:16].upper()
    cache.set(f"telegram_link_token:{token}", str(request.user.id), timeout=600)
    return Response({"token": token, "expires_in": 600})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def verify_otp(request):
    """POST /api/auth/verify-otp/ — Vérifie le code OTP"""
    email = request.data.get("email")
    code  = request.data.get("code")
    user  = User.objects.filter(email=email).first()

    if not user or user.otp_code != code:
        return Response({"error": "Code invalide."}, status=400)

    if user.otp_expires_at < timezone.now():
        return Response({"error": "Code expiré."}, status=400)

    user.is_verified = True
    user.otp_code    = ""
    user.save(update_fields=["is_verified", "otp_code"])
    return Response({"message": "Email vérifié."})


def _get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# ─────────────────────────────────────────────────────────────
# apps/users/urls.py
# ─────────────────────────────────────────────────────────────

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns_users = [
    path("register/",            RegisterView.as_view(),           name="auth-register"),
    path("login/",               TokenObtainPairView.as_view(),    name="auth-login"),
    path("token/refresh/",       TokenRefreshView.as_view(),       name="token-refresh"),
    path("logout/",              logout_view,                      name="auth-logout"),
    path("profile/",             ProfileView.as_view(),            name="auth-profile"),
    path("change-password/",     ChangePasswordView.as_view(),     name="auth-change-password"),
    path("verify-otp/",          verify_otp,                       name="auth-verify-otp"),
    path("telegram-link-token/", generate_telegram_link_token,     name="telegram-link-token"),
]
