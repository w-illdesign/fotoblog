from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Vues d'authentification
from authentification.views import LoginPageView, LogoutUserView, SignupPageView

# Vues du blog
from blog.views import HomeView, UpdateProfilePhotoView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Login
    path('', LoginPageView.as_view(), name='login'),

    # Logout
    path('logout/', LogoutUserView.as_view(), name='logout'),

    # Inscription
    path('signup/', SignupPageView.as_view(), name='signup'),

    # Page d'accueil
    path('home/', HomeView.as_view(), name='home'),

    # Mise à jour de la photo de profil
    path('update-profile-photo/', UpdateProfilePhotoView.as_view(), name='update_profile_photo'),
]

# Sert les fichiers médias uniquement en DEV
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)