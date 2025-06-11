from django.utils import timezone
from django.db import transaction
from backend.models import Document
from kkm.models import ReceiptItemBuffer, CashShift, CashSession


class CashShiftService:
    def __init__(self, shift: CashShift):
        self.shift = shift
        self.register = shift.cash_register
        self.company = shift.company
        self.firm = shift.firm

    @staticmethod
    def open_shift(register, user):
        # Перевірка або створення сесії на сьогодні
        session, _ = CashSession.objects.get_or_create(
            company=register.company,
            firm=register.firm,
            trade_point=register.trade_point,
            is_closed=False,
            defaults={"opened_by": user}
        )

        # Заборона відкривати дві зміни одночасно на одній касі
        if CashShift.objects.filter(cash_register=register, is_closed=False).exists():
            raise Exception("Зміна вже відкрита")

        # Створення зміни
        shift = CashShift.objects.create(
            cash_register=register,
            company=register.company,
            firm=register.firm,
            session=session,
            opened_by=user
        )
        return shift

    @transaction.atomic
    def close_shift(self, user):
        if self.shift.is_closed:
            raise Exception("Зміна вже закрита")

        buffer_items = ReceiptItemBuffer.objects.filter(shift=self.shift)

        if buffer_items.exists():
            # Автоматична очистка буфера, якщо щось залишилось після print-receipts
            buffer_items.delete()

        # Закриття зміни без створення документа, якщо продажі вже були оформлені через print-receipts
        self._finalize_shift(user)
        self._maybe_close_session(user)

        return None

    def _finalize_shift(self, user):
        self.shift.is_closed = True
        self.shift.closed_by = user
        self.shift.closed_at = timezone.now()
        self.shift.save()

    def _maybe_close_session(self, user):
        session = self.shift.session
        if session and not session.shifts.filter(is_closed=False).exists():
            from kkm.service.kkm.cash_session import CashSessionService
            CashSessionService(session).close_session(user)
