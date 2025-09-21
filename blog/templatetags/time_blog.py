from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()

@register.filter
def facebook_time(value):
    """
    Affichage style "Facebook" :
      - À l’instant / Il y a X minutes / Il y a X heures
      - Hier à HH:MM
      - Avant-hier à HH:MM
      - Lundi à HH:MM (si < 7 jours)
      - 18 Sep 2025 à HH:MM (sinon)
    """
    # normaliser maintenant et la valeur dans le même fuseau local
    now_local = timezone.localtime(timezone.now())

    # si value est naive, on l'assume dans le fuseau courant (changer si tu veux UTC)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())

    value_local = timezone.localtime(value)

    delta = now_local - value_local
    seconds = delta.total_seconds()

    # Cas improbable : datetime dans le futur (souvent dû à un problème de TZ)
    if seconds < 0:
        # si léger futur, afficher "À l'instant", sinon afficher la date absolue
        if seconds > -60:
            return "À l’instant"
        return date_format(value_local, 'd M Y à H:i')

    # différence en jours basée sur les dates (plus fiable pour "hier / avant-hier")
    days_diff = (now_local.date() - value_local.date()).days

    if seconds < 60:
        return "À l’instant"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"Il y a {minutes} minute{'s' if minutes > 1 else ''}"
    # s'assurer que c'est bien le même jour pour ne pas confondre "24h" et "hier"
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