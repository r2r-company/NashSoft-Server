from django.contrib import messages
from django.core.exceptions import ValidationError
from backend.services.factory import get_document_service

def try_post_document_if_needed(request, obj, form, old_status):
    new_status = form.cleaned_data.get("status")
    if old_status != 'posted' and new_status == 'posted':
        try:
            service = get_document_service(obj)
            service.post()
            messages.success(request, f"✅ Документ {obj.doc_number} проведено через сервіс.")
        except ValidationError as e:
            messages.error(request, f"❌ Помилка проведення: {e.messages}")
        except Exception as e:
            messages.error(request, f"❌ Внутрішня помилка: {str(e)}")
