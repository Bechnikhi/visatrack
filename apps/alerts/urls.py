from django.urls import path
from .views import AlertListView, NotifPreferenceView

urlpatterns = [
    path("",             AlertListView.as_view(),      name="alerts-list"),
    path("preferences/", NotifPreferenceView.as_view(), name="alerts-preferences"),
]
