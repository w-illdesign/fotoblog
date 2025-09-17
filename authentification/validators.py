# authentification/validators.py
from django.core.exceptions import ValidationError
import re

# Liste des conditions à afficher au front
PASSWORD_CONDITIONS = [
    {"key": "length", "label": "Au moins 6 caractères"},
    {"key": "uppercase", "label": "Au moins une lettre majuscule"},
    {"key": "lowercase", "label": "Au moins une lettre minuscule"},
    {"key": "number", "label": "Au moins un chiffre"},
]

class CustomPasswordValidator:
    def validate(self, password, user=None):
        # Vérifie la longueur
        if len(password) < 6:
            raise ValidationError("Le mot de passe doit contenir au moins 6 caractères.")

        # Vérifie au moins une majuscule
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Le mot de passe doit contenir au moins une lettre majuscule.")

        # Vérifie au moins une minuscule
        if not re.search(r"[a-z]", password):
            raise ValidationError("Le mot de passe doit contenir au moins une lettre minuscule.")

        # Vérifie au moins un chiffre
        if not re.search(r"[0-9]", password):
            raise ValidationError("Le mot de passe doit contenir au moins un chiffre.")

    def get_help_text(self):
        return "Votre mot de passe doit contenir au moins 6 caractères, une majuscule, une minuscule et un chiffre."