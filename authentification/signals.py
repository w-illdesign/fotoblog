# authentification/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Permission
from .models import User

@receiver(post_save, sender=User)
def give_permissions_to_creator(sender, instance, created, **kwargs):
    if created and getattr(instance, 'role', None) == 'Creator':
        add_blog = Permission.objects.get(codename='add_blog')
        delete_blog = Permission.objects.get(codename='delete_blog')
        instance.user_permissions.add(add_blog, delete_blog)