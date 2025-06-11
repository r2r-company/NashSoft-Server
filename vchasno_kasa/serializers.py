from rest_framework import serializers

class VchasnoSystemRequestSerializer(serializers.Serializer):
    idCashRegister = serializers.UUIDField()
    task = serializers.ChoiceField(choices=[18, 20, 21, 22, 23])
    tag = serializers.CharField(required=False)
