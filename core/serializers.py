from rest_framework import serializers
from .models import DemandeActe

class DemandeActeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandeActe
        fields = '__all__'

from rest_framework import serializers
from .models import StructureAdministrative

class StructureAdministrativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StructureAdministrative
        fields = '__all__'
