from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import VchasnoSystemRequestSerializer
from .services.services import send_vchasno_task


class VchasnoSystemTaskView(APIView):
    def post(self, request):
        serializer = VchasnoSystemRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            extra = {}
            if data.get("tag"):
                extra["tag"] = data["tag"]

            result = send_vchasno_task(data["task"], str(data["idCashRegister"]), extra_data=extra)
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
