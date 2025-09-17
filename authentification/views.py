from django.shortcuts import redirect
from django.contrib.auth import login, logout
from django.views.generic import FormView, View
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm  # formulaire intégré

class LoginPageView(FormView):
    template_name = "authentification/login.html"
    form_class = AuthenticationForm
    success_url = reverse_lazy("home")

    # Redirige un utilisateur déjà connecté
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # AuthenticationForm a déjà vérifié les identifiants
        login(self.request, form.get_user())
        return super().form_valid(form)


class LogoutUserView(View):
    def get(self, request):
        logout(request)
        return redirect("login")