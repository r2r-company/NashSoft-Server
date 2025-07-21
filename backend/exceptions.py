from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.response import Response


class BusinessLogicError(Exception):
    """Базовий клас для бізнес-логічних помилок"""
    default_message = "Помилка бізнес-логіки"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message=None, status_code=None):
        self.message = message or self.default_message
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class InsufficientStockError(BusinessLogicError):
    """Недостатньо товару на складі"""
    default_message = "Недостатньо товару на складі"


class DocumentAlreadyPostedException(BusinessLogicError):
    """Документ вже проведено"""
    default_message = "Документ вже проведено"
    status_code = status.HTTP_409_CONFLICT


class DocumentNotPostedException(BusinessLogicError):
    """Документ не проведено"""
    default_message = "Документ не проведено"


class InvalidDocumentTypeError(BusinessLogicError):
    """Невірний тип документа"""
    default_message = "Невірний тип документа"


class PriceNotFoundError(BusinessLogicError):
    """Ціна не знайдена"""
    default_message = "Ціна не знайдена для товару"
    status_code = status.HTTP_404_NOT_FOUND


class ValidationError(BusinessLogicError):
    """Помилка валідації"""
    default_message = "Помилка валідації даних"


class ConfigurationError(BusinessLogicError):
    """Помилка конфігурації"""
    default_message = "Помилка конфігурації системи"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


def custom_exception_handler(exc, context):
    """Кастомний обробник винятків"""

    # Спочатку викликаємо стандартний обробник DRF
    response = exception_handler(exc, context)

    # Якщо це наш кастомний виняток
    if isinstance(exc, BusinessLogicError):
        return Response({
            'success': False,
            'error': exc.message,
            'error_type': exc.__class__.__name__
        }, status=exc.status_code)

    # Якщо response є (стандартний DRF exception)
    if response is not None:
        return Response({
            'success': False,
            'error': response.data,
            'error_type': 'APIException'
        }, status=response.status_code)

    # Для інших винятків
    return Response({
        'success': False,
        'error': 'Внутрішня помилка сервера',
        'error_type': 'ServerError'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvalidReturnQuantityError(BusinessLogicError):
    """Неправильна кількість для повернення"""
    default_message = "Неправильна кількість для повернення товару"

class MissingSourceDocumentError(BusinessLogicError):
    """Відсутній документ-джерело"""
    default_message = "Документ-джерело не вказано або неправильний"

class ConversionValidationError(BusinessLogicError):
    """Помилка валідації фасування"""
    default_message = "Помилка валідації документа фасування"