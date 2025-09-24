import os

def user_directory_path(instance, filename):
    """
    Définit le chemin en fonction de l'utilisateur et du type d'image.
    """
    # Photo de profil (User)
    if hasattr(instance, 'username') or hasattr(instance, 'profile_photo'):
        return os.path.join(instance.username, "Mes_Profils", filename)

    # Photo normale (Photo)
    if hasattr(instance, 'uploader'):
        return os.path.join(instance.uploader.username, "Mes_photos", filename)

    # fallback
    return os.path.join("others", filename)
    
    
# blog/utils.py
from django.utils import timezone
from django.utils.formats import date_format

def facebook_time(value):
    """
    Même logique que ton filter : renvoie le label 'À l’instant', 'Il y a X minutes', etc.
    """
    if value is None:
        return ""

    now_local = timezone.localtime(timezone.now())

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())

    value_local = timezone.localtime(value)
    delta = now_local - value_local
    seconds = delta.total_seconds()

    if seconds < 0:
        if seconds > -60:
            return "À l’instant"
        return date_format(value_local, 'd M Y à H:i')

    days_diff = (now_local.date() - value_local.date()).days

    if seconds < 60:
        return "À l’instant"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"Il y a {minutes} minute{'s' if minutes > 1 else ''}"
    if seconds < 86400 and days_diff == 0:
        hours = int(seconds // 3600)
        return f"Il y a {hours} heure{'s' if hours > 1 else ''}"
    if days_diff == 1:
        return f"Hier à {date_format(value_local, 'H:i')}"
    if days_diff == 2:
        return f"Avant-hier à {date_format(value_local, 'H:i')}"
    if days_diff < 7:
        return f"{date_format(value_local, 'l')} à {date_format(value_local, 'H:i')}"
    return date_format(value_local, 'd M Y à H:i')    