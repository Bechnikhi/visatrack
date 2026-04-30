from django.urls import path
from .views import (VisaCenterListView, SlotListView, VisaRequestListCreateView,
                    VisaRequestDetailView, MonitoringLogListView, CountryListView)

urlpatterns = [
    path("countries/",           CountryListView.as_view(),            name="countries-list"),
    path("centers/",             VisaCenterListView.as_view(),         name="centers-list"),
    path("slots/",               SlotListView.as_view(),               name="slots-list"),
    path("requests/",            VisaRequestListCreateView.as_view(),  name="requests-list"),
    path("requests/<uuid:pk>/",  VisaRequestDetailView.as_view(),      name="requests-detail"),
    path("logs/",                MonitoringLogListView.as_view(),      name="logs-list"),
]
