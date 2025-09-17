from django.shortcuts import redirect
from django.contrib.auth import login, logout
from django.views.generic import FormView, View
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm
from .forms import SignupForm
from .validators import PASSWORD_CONDITIONS  # <-- import tes règles définies dans validators.py


class SignupPageView(FormView):
    template_name = "authentification/signup.html"
    form_class = SignupForm
    success_url = "/home/"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On envoie les conditions au template
        context['password_conditions'] = PASSWORD_CONDITIONS
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
        
        
class LoginPageView(FormView):
    template_name = "authentification/login.html"
    form_class = AuthenticationForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)


class LogoutUserView(View):
    def get(self, request):
        logout(request)
        return redirect("login")
