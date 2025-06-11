from django.shortcuts import get_object_or_404
from kkm.models import CashWorkstation

def get_workstation(request):
    app_key = request.data.get("app_key") or request.query_params.get("app_key")
    pc_name = request.data.get("pc_name") or request.query_params.get("pc_name")

    if app_key:
        return get_object_or_404(CashWorkstation, app_key=app_key, active=True)
    elif pc_name:
        return get_object_or_404(CashWorkstation, name__iexact=pc_name.strip(), active=True)

    raise ValueError("Не передано ні APP_KEY, ні pc_name")
