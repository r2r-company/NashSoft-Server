# backend/auth.py
from functools import wraps

from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers, status

from django.contrib.auth import authenticate, get_user_model
from backend.models import AppUser  # твоя модель "Користувач"

User = get_user_model()

class CustomLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    interface = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        interface_code = attrs.get("interface")

        user = authenticate(username=username, password=password)

        if user is None:
            raise serializers.ValidationError("Невірний логін або пароль")

        try:
            # знаходимо AppUser, в якого є потрібний interface
            app_user = AppUser.objects.get(
                user=user,
                is_active=True,
                interfaces__code=interface_code
            )
        except AppUser.DoesNotExist:
            raise serializers.ValidationError("Немає доступу до вказаного інтерфейсу")

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "username": user.username,
            "interface": interface_code,
            "app_user_id": app_user.id,
            "company_id": app_user.company.id if app_user.company else None,
            "company_name": app_user.company.name if app_user.company else None,
            "access_granted": app_user.is_active,
        }


def require_custom_right(required_right: str):
    """
    Перевіряє наявність кастомного права (з AccessGroup.rights) для активного інтерфейсу користувача
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            user = request.user

            app_users = AppUser.objects.filter(user=user, is_active=True).prefetch_related(
                "interfaces__access_group__rights"
            )

            for app_user in app_users:
                for interface in app_user.interfaces.all():
                    access_group = interface.access_group
                    if access_group and access_group.rights.filter(code=required_right).exists():
                        return view_func(self, request, *args, **kwargs)

            return Response(
                {"detail": f"Недостатньо прав: {required_right}"},
                status=status.HTTP_403_FORBIDDEN
            )

        return _wrapped_view
    return decorator