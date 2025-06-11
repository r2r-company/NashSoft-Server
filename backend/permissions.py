# backend/permissions.py (або mixins.py)

from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from backend.models import AppUser

class InterfaceRequiredMixin:
    permission_classes = [IsAuthenticated]  # обов'язковий вхід

    required_interface = None  # 👈 вказуєш у View

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        user = request.user
        interface = getattr(self, "required_interface", None)

        if not interface:
            raise PermissionDenied("Інтерфейс не вказано в класі View")

        if not AppUser.objects.filter(
            user=user,
            is_active=True,
            interfaces__code=interface
        ).exists():
            raise PermissionDenied(f"Немає доступу до інтерфейсу '{interface}'")
