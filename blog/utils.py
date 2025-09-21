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