# blog/views.py
from django.views.generic import TemplateView
from django.views import View
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin

class HomeView(LoginRequiredMixin, TemplateView):
    """
    Page d'accueil du blog. Nécessite que l'utilisateur soit connecté.
    Passe la photo de profil au template.
    """
    template_name = 'blog/home.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On fournit la photo de profil à template
        context['profile_photo'] = self.request.user.profile_photo
        return context


class UpdateProfilePhotoView(LoginRequiredMixin, View):
    """
    Permet à l'utilisateur de mettre à jour sa photo de profil via POST.
    """
    login_url = 'login'

    def post(self, request, *args, **kwargs):
        # Récupère le fichier uploadé
        photo = request.FILES.get("profile_photo")
        if photo:
            request.user.profile_photo = photo
            request.user.save()
        # Redirige vers la page d'accueil après upload
        return redirect("home")