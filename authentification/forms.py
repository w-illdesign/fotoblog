from django import forms
from .models import User
from django.contrib.auth.forms import UserCreationForm

class SignupForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True,
        widget=forms.HiddenInput()  # on cache l'input natif
    )

    class Meta:
        model = User
        fields = ("username", "email", "role", "password1", "password2")
        

        
          