from django.contrib.auth.forms import UserCreationForm
from .models import User

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Commune  # Adapte selon tes modèles

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    commune = forms.ModelChoiceField(queryset=Commune.objects.all(), required=True, label="Commune")
    numero_cni = forms.CharField(max_length=20, required=False, label="Numéro CNI")  # Optionnel

    class Meta:
        model = User
        fields = ['username', 'email', 'commune', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'CITOYEN'
        user.is_active = False
        user.statut = 'EAQUIPE'
        if commit:
            user.save()
        return user



  # forms.py
from django import forms
from .models import Paiement, Tarif

from django import forms
from core.models import Paiement, Tarif

from django import forms
from .models import Paiement

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = '__all__'
        widgets = {
            'montant': forms.NumberInput(attrs={'readonly': 'readonly'}),
            'montant_timbres': forms.NumberInput(attrs={'readonly': 'readonly'}),
            'montant_total': forms.NumberInput(attrs={'readonly': 'readonly'}),
        }


