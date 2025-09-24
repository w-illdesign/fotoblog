from django.shortcuts import redirect
from django.contrib.auth import login, logout
from django.views.generic import FormView, View
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction, OperationalError
from .forms import SignupForm
from .validators import PASSWORD_CONDITIONS
from .models import User
import time


class SignupPageView(FormView):
    template_name = "authentification/signup.html"
    form_class = SignupForm
    success_url = "/"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_conditions'] = PASSWORD_CONDITIONS
        return context

    def form_valid(self, form):
        username = form.cleaned_data.get("username")

        # Essayer jusqu'à 3 fois si la DB est lockée
        for attempt in range(3):
            try:
                with transaction.atomic():
                    if User.objects.filter(username=username).exists():
                        form.add_error('username', 'Ce nom d’utilisateur existe déjà.')
                        return self.form_invalid(form)
                    user = form.save()
                break
            except OperationalError:
                # petite pause avant de réessayer
                time.sleep(0.1)
        else:
            form.add_error(None, "Impossible de créer le compte, réessayez plus tard.")
            return self.form_invalid(form)

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
        return redirect("/")
