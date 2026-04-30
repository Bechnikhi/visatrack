# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Admin Django
    path("admin/", admin.site.urls),

    # API v1
    path("api/auth/",       include("apps.users.urls")),
    path("api/monitoring/", include("apps.monitoring.urls")),
    path("api/alerts/",     include("apps.alerts.urls")),
    path("api/billing/",    include("apps.billing.urls")),
    path("api/bot/",        include("apps.bot.urls")),

    # Documentation API
    path("api/schema/",         SpectacularAPIView.as_view(),         name="schema"),
    path("api/docs/",           SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
