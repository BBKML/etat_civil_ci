from django.contrib.auth.forms import UserCreationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'numero_cni')
    def save(self, commit=True):
        user = super().save(commit=False)  # Crée l'objet user sans l'enregistrer
        user.is_staff = True  # Force is_staff=True
        if commit:
            user.save()
        return user