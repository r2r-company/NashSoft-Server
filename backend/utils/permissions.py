from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from backend.models import AppUser


def require_document_permission(doc_type: str, action: str):
    """
    Загальний декоратор для перевірки прав доступу на створення/перегляд/редагування/видалення документа.
    Права доступу будуть виглядати так: create_{doc_type}, view_{doc_type}, edit_{doc_type}, delete_{doc_type}
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            user = request.user

            # Перевіряємо чи користувач має активний профіль в AppUser
            try:
                app_user = AppUser.objects.get(user=user, is_active=True)
            except AppUser.DoesNotExist:
                return Response(
                    {"detail": "Користувач не знайдений або не має активного профілю."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Формуємо назву права для перевірки
            required_permission = f"{action}_{doc_type}"

            # Перевіряємо чи є у користувача доступ до цього права через інтерфейс
            has_permission = False
            for interface in app_user.interfaces.all():
                group = interface.access_group  # Отримуємо групу прав
                if group and group.permissions.filter(codename=required_permission).exists():
                    has_permission = True
                    break

            if not has_permission:
                return Response(
                    {"detail": f"Недостатньо прав для виконання операції: {required_permission}"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Якщо права є, продовжуємо виконання функції
            return view_func(self, request, *args, **kwargs)

        return _wrapped_view
    return decorator
