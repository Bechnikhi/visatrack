from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, ProfileView, ChangePasswordView, logout_view, verify_otp, generate_telegram_link_token

urlpatterns = [
    path("register/",            RegisterView.as_view(),       name="auth-register"),
    path("login/",               TokenObtainPairView.as_view(), name="auth-login"),
    path("token/refresh/",       TokenRefreshView.as_view(),   name="token-refresh"),
    path("logout/",              logout_view,                  name="auth-logout"),
    path("profile/",             ProfileView.as_view(),        name="auth-profile"),
    path("change-password/",     ChangePasswordView.as_view(), name="auth-change-password"),
    path("verify-otp/",          verify_otp,                   name="auth-verify-otp"),
    path("telegram-link-token/", generate_telegram_link_token, name="telegram-link-token"),
]
