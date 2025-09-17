from django.contrib import admin
from django.urls import path
import blog.views
from authentification.views import LoginPageView, LogoutUserView
from blog.views import HomeView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Login avec ta CBV personnalisée
    path('', LoginPageView.as_view(), name='login'),

    # Logout avec ta CBV
    path('logout/', LogoutUserView.as_view(), name='logout'),

    # Page d’accueil
    path('home/', HomeView.as_view(), name='home'),
]

