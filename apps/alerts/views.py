from rest_framework import generics, permissions
from .models import Alert, NotificationPreference
from .serializers import AlertSerializer, NotifPreferenceSerializer

class AlertListView(generics.ListAPIView):
    serializer_class   = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by("-created_at")[:50]

class NotifPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class   = NotifPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj
