from django.contrib.auth.models import AbstractUser
from django.db import models
from PIL import Image
from blog.utils import user_directory_path  # <-- importer utils ici


class User(AbstractUser):
    CREATOR = "Creator"
    SUBSCRIBER = "Subscriber"

    ROLE_CHOICES = (
        (CREATOR, "Créateur"),
        (SUBSCRIBER, "Abonné"),
    )

    IMAGE_MAX_SIZE = (400, 400)  # 👈 un peu plus petit que les photos normales

    profile_photo = models.ImageField(
        upload_to=user_directory_path,
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
    
    follows = models.ManyToManyField(
        "self",
        limit_choices_to={"role": CREATOR},
        symmetrical=False,
        verbose_name="suit",
        related_name="followers"  # ✅ permet d’accéder à creator.followers
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    def save(self, *args, **kwargs):
        """Redimensionnement automatique de la photo de profil"""
        super().save(*args, **kwargs)  # d’abord sauvegarder l’original

        if self.profile_photo:
            image = Image.open(self.profile_photo.path)
            if image.height > self.IMAGE_MAX_SIZE[1] or image.width > self.IMAGE_MAX_SIZE[0]:
                image.thumbnail(self.IMAGE_MAX_SIZE)
                image.save(self.profile_photo.path)