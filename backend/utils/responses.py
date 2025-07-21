from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator
from typing import Any, Dict, Optional


class StandardResponse:
    """Стандартизовані відповіді API"""

    @staticmethod
    def success(data: Any = None, message: str = "", status_code: int = status.HTTP_200_OK,
                meta: Dict = None) -> Response:
        """Успішна відповідь"""
        response_data = {
            "success": True,
            "data": data,
        }

        if message:
            response_data["message"] = message

        if meta:
            response_data["meta"] = meta

        return Response(response_data, status=status_code)

    @staticmethod
    def created(data: Any = None, message: str = "Створено успішно", resource_id: Any = None) -> Response:
        """Відповідь для створення ресурсу"""
        response_data = {
            "success": True,
            "data": data,
            "message": message,
        }

        if resource_id:
            response_data["resource_id"] = resource_id

        return Response(response_data, status=status.HTTP_201_CREATED)

    @staticmethod
    def updated(data: Any = None, message: str = "Оновлено успішно") -> Response:
        """Відповідь для оновлення ресурсу"""
        return StandardResponse.success(data, message, status.HTTP_200_OK)

    @staticmethod
    def deleted(message: str = "Видалено успішно") -> Response:
        """Відповідь для видалення ресурсу"""
        return Response({
            "success": True,
            "message": message
        }, status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def error(message: str, error_code: str = None, details: Any = None,
              status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Відповідь з помилкою"""
        response_data = {
            "success": False,
            "error": message,
        }

        if error_code:
            response_data["error_code"] = error_code

        if details:
            response_data["details"] = details

        return Response(response_data, status=status_code)

    @staticmethod
    def not_found(message: str = "Ресурс не знайдено", resource: str = None) -> Response:
        """Відповідь 404"""
        error_msg = f"{resource} не знайдено" if resource else message
        return StandardResponse.error(error_msg, "NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

    @staticmethod
    def forbidden(message: str = "Доступ заборонено") -> Response:
        """Відповідь 403"""
        return StandardResponse.error(message, "FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def paginated(queryset, request, serializer_class, page_size: int = 20, message: str = "") -> Response:
        """Пагінована відповідь"""
        paginator = Paginator(queryset, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        serializer = serializer_class(page_obj, many=True, context={'request': request})

        meta = {
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "page_size": page_size,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        }

        return StandardResponse.success(serializer.data, message, meta=meta)


class DocumentActionResponse:
    """Спеціальні відповіді для дій з документами"""

    @staticmethod
    def posted(doc_number: str, doc_type: str = "Документ") -> Response:
        """Документ проведено"""
        return StandardResponse.success(
            data={"doc_number": doc_number, "status": "posted"},
            message=f"{doc_type} {doc_number} успішно проведено"
        )

    @staticmethod
    def unposted(doc_number: str, doc_type: str = "Документ") -> Response:
        """Документ розпроведено"""
        return StandardResponse.success(
            data={"doc_number": doc_number, "status": "draft"},
            message=f"{doc_type} {doc_number} успішно розпроведено"
        )

    @staticmethod
    def approved(doc_number: str, doc_type: str = "Документ") -> Response:
        """Документ затверджено"""
        return StandardResponse.success(
            data={"doc_number": doc_number, "status": "approved"},
            message=f"{doc_type} {doc_number} успішно затверджено"
        )