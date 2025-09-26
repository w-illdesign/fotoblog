# create_20_users_valid_passwords.py
import os
import django
import random
import string

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fotoblog.settings")
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

# --- Utilisateurs de base ---
usernames = [
    "Shadow", 
    "Blaze", 
    "Viper", 
    "Rogue", 
    "Phoenix",
    "Nova", 
    "Will",
    "Ghost",
    "Ace",
    "Storm",
    
    "Falcon",
    "Zephyr",
    "Orion", 
    "Luna",
    "Sable",
    "Echo",
    "Onyx", 
    "Titan", 
    "Jade",
    "Raven"
]

emails = [f"willx{u.lower()}@gmail.com" for u in usernames]

# --- Choisir 5 créateurs au hasard ---
creator_indices = set(random.sample(range(20), 5))

# --- Générer mot de passe valide pour chaque utilisateur ---
def generate_password():
    # 6 caractères minimum, une majuscule, une minuscule, un chiffre
    letters_lower = random.choice(string.ascii_lowercase)
    letters_upper = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    other_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
    password = letters_upper + letters_lower + digit + other_chars
    return ''.join(random.sample(password, len(password)))  # mélange

for idx, username in enumerate(usernames):
    email = emails[idx]
    role = User.CREATOR if idx in creator_indices else User.SUBSCRIBER
    password = generate_password()

    if not User.objects.filter(username=username).exists():
        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role
        )
        print(f"✅ {username} créé ! Rôle : {role}, Email : {email}, Mot de passe : {password}")
    else:
        print(f"⚠️ {username} déjà présent")