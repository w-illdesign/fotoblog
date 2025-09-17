from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    CREATOR = "Creator"
    SUBSCRIBER = "Subscriber"

    ROLE_CHOICES = (
        (CREATOR, "Créateur"),
        (SUBSCRIBER, "Abonné"),
    )

    profile_photo = models.ImageField(
        upload_to="profiles/",  # dossier où les images seront stockées
        verbose_name="Photo de profil",
        blank=True,
        null=True
    )
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        verbose_name="Rôle",
        default=SUBSCRIBER
    )

    def __str__(self):
        return f"{self.username} ({self.role})"