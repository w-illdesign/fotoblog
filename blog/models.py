from django.conf import settings
from django.db import models
from .utils import user_directory_path  # <-- import de notre fonction

class Photo(models.Model):
    image = models.ImageField(upload_to=user_directory_path)  # <-- utiliser la fonction ici
    caption = models.CharField(max_length=128, blank=True)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.caption[:20]}"

    def likes_count(self):
        return self.likes.count()


class Like(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('photo', 'user')

    def __str__(self):
        return f"{self.user.username} aime {self.photo.caption[:20]}"


class Blog(models.Model):
    photo = models.ForeignKey(Photo, null=True, on_delete=models.SET_NULL, blank=True)
    title = models.CharField(max_length=128)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    starred = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} par {self.author.username}"