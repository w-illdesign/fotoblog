# blog/models.py
from django.conf import settings
from django.db import models
from PIL import Image
from .utils import user_directory_path
from taggit.managers import TaggableManager  # <-- import pour les tags


class Photo(models.Model):
    IMAGE_MAX_SIZE = (800, 800)

    image = models.ImageField(upload_to=user_directory_path)
    caption = models.CharField(max_length=128, blank=True)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    # --- Nouveau champ tags ---
    tags = TaggableManager(blank=True)

    def __str__(self):
        return f"{self.caption[:20]}"

    def likes_count(self):
        return self.likes.count()

    def save(self, *args, **kwargs):
        """Redimensionnement automatique de l’image"""
        super().save(*args, **kwargs)
        if self.image:
            image = Image.open(self.image.path)
            if image.height > self.IMAGE_MAX_SIZE[1] or image.width > self.IMAGE_MAX_SIZE[0]:
                image.thumbnail(self.IMAGE_MAX_SIZE)
                image.save(self.image.path)


class Like(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('photo', 'user')

    def __str__(self):
        return f"{self.user.username} aime {self.photo.caption[:20]}"


class Blog(models.Model):
    photo = models.ForeignKey(Photo, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=128)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    starred = models.BooleanField(default=False)

    # --- Nouveau champ tags ---
    tags = TaggableManager(blank=True)

    def __str__(self):
        return f"{self.title} par {self.author.username}"