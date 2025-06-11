from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from kkm.service.kkm.cash_session import CashSessionService
from kkm.views import get_workstation_from_request


class CloseSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        workstation = get_workstation_from_request(request)
        session = workstation.cash_register.session_set.filter(is_closed=False).first()
        if not session:
            return Response({"error": "Немає відкритої сесії"}, status=400)

        CashSessionService(session).close_session(request.user)
        return Response({"message": "Сесію закрито. Продажі проведено ✅"})
