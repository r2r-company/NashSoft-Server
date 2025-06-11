from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from kkm.models import CashShift, CashWorkstation
from kkm.service.kkm.cash_shift import CashShiftService


def get_workstation_from_request(request):
    app_key = request.data.get("app_key") or request.query_params.get("app_key")
    pc_name = request.data.get("pc_name") or request.query_params.get("pc_name")

    if app_key:
        return get_object_or_404(CashWorkstation, app_key=app_key, active=True)
    elif pc_name:
        return get_object_or_404(CashWorkstation, name__iexact=pc_name.strip(), active=True)

    raise ValueError("Не передано APP KEY або pc_name")


class OpenShiftView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        cash_register = workstation.cash_register

        if CashShift.objects.filter(cash_register=cash_register, is_closed=False).exists():
            return Response({"message": "Зміна вже відкрита"}, status=200)

        try:
            shift = CashShiftService.open_shift(cash_register, request.user)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({
            "message": "Зміну відкрито",
            "shift_id": shift.id,
            "opened_at": shift.opened_at,
            "cash_register": cash_register.name
        }, status=201)


class CloseShiftView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        cash_register = workstation.cash_register

        shift = CashShift.objects.filter(
            cash_register=cash_register,
            is_closed=False
        ).order_by("-opened_at").first()

        if not shift:
            return Response({"error": "Відкрита зміна не знайдена"}, status=400)

        try:
            service = CashShiftService(shift)
            document = service.close_shift(request.user)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        if not document:
            return Response({
                "message": "Зміну закрито. Продажів не було.",
                "closed_at": shift.closed_at
            }, status=200)

        return Response({
            "message": "Зміну закрито і сформовано документ продажу.",
            "document_id": document.id,
            "doc_number": document.doc_number,
            "closed_at": shift.closed_at,
            "items": [
                {
                    "product": item.product.name,
                    "quantity": item.quantity,
                    "price": float(item.price)
                } for item in document.items.all()
            ]
        }, status=200)


class ShiftStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        cash_register = workstation.cash_register
        shift = CashShift.objects.filter(
            cash_register=cash_register,
            is_closed=False
        ).order_by("-opened_at").first()

        if not shift:
            return Response({
                "status": "closed",
                "message": "Зміна не відкрита",
                "cash_register": cash_register.name,
                "workstation": workstation.name,
                "trade_point": cash_register.trade_point.name,
                "firm": cash_register.firm.name,
                "session_status": "невідомо",
                "opened_by": None,
                "opened_at": None
            })

        session = shift.session

        return Response({
            "status": "open",
            "shift_id": shift.id,
            "session_id": session.id if session else None,
            "session_opened_at": session.opened_at if session else None,
            "shift_opened_at": shift.opened_at,
            "opened_by": shift.opened_by.username if shift.opened_by else None,
            "cash_register": cash_register.name,
            "workstation": workstation.name,
            "trade_point": cash_register.trade_point.name,
            "firm": cash_register.firm.name,
            "session_status": "активна" if session and not session.is_closed else "закрита"
        })