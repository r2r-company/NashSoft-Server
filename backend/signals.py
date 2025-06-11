# signals.py
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from backend.models import Document, Operation


@receiver(pre_delete, sender=Document)
def prevent_delete_posted_document(sender, instance, **kwargs):
    if instance.status == 'posted':
        raise ValidationError("Неможливо видалити проведений документ.")


@receiver(pre_delete, sender=Operation)
def prevent_delete_operation_if_used(sender, instance, **kwargs):
    if instance.direction == 'in':
        used_qty = Operation.objects.filter(source_operation=instance, visible=True).count()
        if used_qty > 0:
            raise ValidationError("Неможливо видалити вхідну операцію, яка вже використана у FIFO.")