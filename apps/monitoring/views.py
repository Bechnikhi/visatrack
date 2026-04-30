# apps/monitoring/views.py
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import VisaCenter, AppointmentSlot, VisaRequest, MonitoringLog, Country
from .serializers import (
    VisaCenterSerializer, SlotSerializer,
    VisaRequestSerializer, MonitoringLogSerializer, CountrySerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role in ("admin", "superadmin")


class CountryListView(generics.ListAPIView):
    queryset         = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
    permission_classes = [permissions.IsAuthenticated]


class VisaCenterListView(generics.ListAPIView):
    queryset           = VisaCenter.objects.filter(is_active=True).select_related("country")
    serializer_class   = VisaCenterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields   = ["platform", "country"]
    search_fields      = ["city", "country__name_fr"]


class SlotListView(generics.ListAPIView):
    serializer_class   = SlotSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ["center", "status", "slot_date"]

    def get_queryset(self):
        from django.utils import timezone
        return AppointmentSlot.objects.filter(
            status="available",
            slot_date__gte=timezone.now().date(),
        ).select_related("center__country").order_by("slot_date", "slot_time")


class VisaRequestListCreateView(generics.ListCreateAPIView):
    serializer_class   = VisaRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ("admin", "superadmin"):
            return VisaRequest.objects.all().select_related("user", "center__country")
        return VisaRequest.objects.filter(user=user).select_related("center__country")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, created_by=self.request.user)


class VisaRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = VisaRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ("admin", "superadmin"):
            return VisaRequest.objects.all()
        return VisaRequest.objects.filter(user=user)


class MonitoringLogListView(generics.ListAPIView):
    serializer_class   = MonitoringLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ["center", "success"]

    def get_queryset(self):
        if self.request.user.role not in ("admin", "superadmin"):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        return MonitoringLog.objects.select_related("center").order_by("-checked_at")[:200]
