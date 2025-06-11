# backend/services/logger.py
from backend.models import AuditLog, PriceSettingDocument
from datetime import datetime

class AuditLoggerService:
    def __init__(self, document=None, user=None, ip_address=None, endpoint=None):
        self.document = document
        self.user = user
        self.ip_address = ip_address
        self.endpoint = endpoint

    def log_event(self, action, message):
        # Якщо це подія для документа ціноутворення, створюємо окремий лог
        if isinstance(self.document, PriceSettingDocument):
            log = AuditLog.objects.create(
                action=action,
                message=message,
                document=None,  # Тут ми не передаємо документ типу Document
                price_setting_document=self.document  # Якщо хочете зберігати цю інформацію
            )
        else:
            log = AuditLog.objects.create(
                action=action,
                message=message,
                document=self.document  # Зв'язок з класичним документом
            )

        return log