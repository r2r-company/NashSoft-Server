import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from django.contrib.auth.models import User
from backend.models import AuditLog


class AuditLoggerService:
    """Розширений сервіс для логування подій та помилок"""

    def __init__(self, document=None, price_setting_document=None, user=None, ip_address=None):
        self.document = document
        self.price_setting_document = price_setting_document
        self.user = user
        self.ip_address = ip_address

        # Налаштовуємо Python logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def log_event(self, action: str, message: str, level: str = "INFO", extra_data: Dict = None):
        """Логування звичайних подій"""
        try:
            # Логування в базу даних
            AuditLog.objects.create(
                document=self.document,
                price_setting_document=self.price_setting_document,
                user=self.user,
                ip_address=self.ip_address,
                action=action,
                message=message
            )

            # Логування в файл/консоль - БЕЗ message в extra
            log_data = {
                'action': action,
                'log_message': message,  # ⬅️ ЗМІНИЛИ З 'message' на 'log_message'
                'document_id': self.document.id if self.document else None,
                'document_number': self.document.doc_number if self.document else None,
                'user_id': self.user.id if self.user else None,
                'ip_address': self.ip_address,
                'timestamp': datetime.now().isoformat(),
                'extra_data': extra_data or {}
            }

            if level == "ERROR":
                self.logger.error(f"[{action}] {message}", extra=log_data)
            elif level == "WARNING":
                self.logger.warning(f"[{action}] {message}", extra=log_data)
            else:
                self.logger.info(f"[{action}] {message}", extra=log_data)

        except Exception as e:
            # Фолбек логування якщо основне не працює
            self.logger.error(f"Failed to log event: {str(e)}")

    def log_error(self, action: str, error: Exception, context: Dict = None):
        """Спеціальне логування помилок"""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_args': getattr(error, 'args', []),
            'context': context or {}
        }

        error_message = f"Помилка: {str(error)}"  # ⬅️ ЗМІНИЛИ НАЗВУ ЗМІННОЇ
        self.log_event(action, error_message, level="ERROR", extra_data=error_data)

    def log_validation_error(self, action: str, validation_errors: Dict, context: Dict = None):
        """Логування помилок валідації"""
        error_data = {
            'validation_errors': validation_errors,
            'context': context or {}
        }

        message = f"Помилка валідації: {json.dumps(validation_errors, ensure_ascii=False)}"
        self.log_event(action, message, level="WARNING", extra_data=error_data)

    def log_business_logic_error(self, action: str, business_error: str, details: Dict = None):
        """Логування бізнес-логічних помилок"""
        error_data = {
            'business_error': business_error,
            'details': details or {}
        }

        message = f"Бізнес-помилка: {business_error}"
        self.log_event(action, message, level="WARNING", extra_data=error_data)

    def log_performance(self, action: str, duration_ms: float, details: Dict = None):
        """Логування продуктивності"""
        perf_data = {
            'duration_ms': duration_ms,
            'performance_details': details or {}
        }

        level = "WARNING" if duration_ms > 5000 else "INFO"  # Повільно якщо >5сек
        message = f"Виконання '{action}' зайняло {duration_ms:.2f}мс"
        self.log_event(action, message, level=level, extra_data=perf_data)

    def log_security_event(self, action: str, security_message: str, severity: str = "HIGH"):
        """Логування подій безпеки"""
        security_data = {
            'security_event': True,
            'severity': severity,
            'user_agent': getattr(self, 'user_agent', None),
            'timestamp': datetime.now().isoformat()
        }

        message = f"SECURITY: {security_message}"
        self.log_event(action, message, level="ERROR", extra_data=security_data)

    @classmethod
    def create_from_request(cls, request, document=None, price_setting_document=None):
        """Створити logger з Django request"""
        return cls(
            document=document,
            price_setting_document=price_setting_document,
            user=getattr(request, 'user', None) if hasattr(request, 'user') else None,
            ip_address=cls._get_client_ip(request)
        )

    @staticmethod
    def _get_client_ip(request):
        """Отримати IP адресу клієнта"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PerformanceLogger:
    """Декоратор для логування продуктивності"""

    def __init__(self, action_name: str, logger_service: AuditLoggerService = None):
        self.action_name = action_name
        self.logger_service = logger_service or AuditLoggerService()
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            self.logger_service.log_performance(self.action_name, duration)