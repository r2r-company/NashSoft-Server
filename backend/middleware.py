import logging
import traceback
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from backend.exceptions import BusinessLogicError

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(MiddlewareMixin):
    """Middleware для обробки помилок API"""

    def process_exception(self, request, exception):
        """Обробляє винятки, які не були оброблені views"""

        # Логуємо всі помилки
        logger.error(f"Unhandled exception: {str(exception)}", extra={
            'request_path': request.path,
            'request_method': request.method,
            'user': getattr(request, 'user', None),
            'exception_type': type(exception).__name__,
            'traceback': traceback.format_exc()
        })

        # Обробляємо тільки API запити (JSON)
        if not request.path.startswith('/api/'):
            return None

        # Якщо це наш кастомний виняток - він вже оброблений в exception_handler
        if isinstance(exception, BusinessLogicError):
            return None

        # Для всіх інших помилок повертаємо 500
        return JsonResponse({
            'success': False,
            'error': 'Внутрішня помилка сервера',
            'error_type': 'ServerError',
            'detail': str(exception) if settings.DEBUG else 'Сталася неочікувана помилка'
        }, status=500)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware для логування API запитів"""

    def process_request(self, request):
        """Логує всі API запити"""
        if request.path.startswith('/api/'):
            logger.info(f"API Request: {request.method} {request.path}", extra={
                'user': getattr(request, 'user', None),
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            })

    def process_response(self, request, response):
        """Логує відповіді API"""
        if request.path.startswith('/api/'):
            logger.info(f"API Response: {request.method} {request.path} - {response.status_code}", extra={
                'status_code': response.status_code,
                'user': getattr(request, 'user', None),
            })
        return response

    def get_client_ip(self, request):
        """Отримує IP адресу клієнта"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CORSMiddleware(MiddlewareMixin):
    """Простий CORS middleware для API"""

    def process_response(self, request, response):
        """Додає CORS заголовки"""
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response