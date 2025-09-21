# blog/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, ListView, View, DetailView, UpdateView
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.contrib import messages

from . import forms, models
from .models import Photo, Blog, Like
from .forms import BlogForm, DeleteBlogForm, PhotoForm


# ======================================================
# Page d'accueil
# ======================================================
class HomeView(LoginRequiredMixin, ListView):
    model = Photo
    template_name = "blog/home.html"
    context_object_name = "photos"
    ordering = ["-id"]
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile_photo"] = getattr(self.request.user, "profile_photo", None)

        user = self.request.user
        photo_likes = {
            photo.id: photo.likes.filter(user=user).exists()
            for photo in context["photos"]
        }
        context["photo_likes"] = photo_likes
        return context


class BlogDetailView(LoginRequiredMixin, DetailView):
    model = Blog
    template_name = "blog/view_blog.html"
    context_object_name = "blog"
    pk_url_kwarg = "blog_id"
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        photo = getattr(self.object, "photo", None)
        context["user_liked"] = photo.likes.filter(user=user).exists() if photo else False
        context["likes_count"] = photo.likes.count() if photo else 0
        context["profile_photo"] = getattr(user, "profile_photo", None)
        return context


# ======================================================
# Upload de photo simple
# ======================================================
class PhotoUploadView(LoginRequiredMixin, CreateView):
    model = Photo
    form_class = forms.PhotoForm
    template_name = "blog/photo_upload.html"
    success_url = reverse_lazy("home")
    login_url = "login"

    def form_valid(self, form):
        form.instance.uploader = self.request.user
        messages.success(self.request, "Photo téléchargée avec succès.")
        return super().form_valid(form)


# ======================================================
# Mise à jour photo de profil
# ======================================================
class UpdateProfilePhotoView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request, *args, **kwargs):
        photo = request.FILES.get("profile_photo")
        if photo:
            request.user.profile_photo = photo
            request.user.save()
            messages.success(request, "Photo de profil mise à jour.")
        return redirect("home")


# ======================================================
# Création blog + photo
# ======================================================
class BlogAndPhotoUploadView(LoginRequiredMixin, View):
    login_url = "login"

    def get(self, request, *args, **kwargs):
        return render(request, "blog/create_blog_post.html", {
            "blog_form": forms.BlogForm(),
            "photo_form": forms.PhotoForm(),
        })

    def post(self, request, *args, **kwargs):
        blog_form = forms.BlogForm(request.POST)
        photo_form = forms.PhotoForm(request.POST, request.FILES)

        if blog_form.is_valid() and photo_form.is_valid():
            try:
                with transaction.atomic():
                    # Sauvegarde photo
                    photo = photo_form.save(commit=False)
                    photo.uploader = request.user
                    photo.save()

                    # Sauvegarde blog
                    blog = blog_form.save(commit=False)
                    blog.author = request.user
                    blog.photo = photo
                    blog.save()

                messages.success(request, "Billet publié avec succès.")
                return redirect("home")

            except Exception as e:
                # log/print pour debug ; remplace par logger si tu en as un
                print("Erreur lors de la sauvegarde du billet :", e)
                messages.error(request, "Erreur lors de la publication. Réessaye.")

        # Debug : afficher erreurs en console (optionnel)
        if not blog_form.is_valid():
            print("BlogForm errors:", blog_form.errors)
        if not photo_form.is_valid():
            print("PhotoForm errors:", photo_form.errors)

        return render(request, "blog/create_blog_post.html", {
            "blog_form": blog_form,
            "photo_form": photo_form,
        })


# ======================================================
# Like / Unlike AJAX
# ======================================================
class ToggleLikeView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request, *args, **kwargs):
        photo_id = kwargs.get("photo_id") or request.POST.get("photo_id")
        if not photo_id:
            return JsonResponse({"error": "photo_id manquant"}, status=400)

        photo = get_object_or_404(Photo, id=photo_id)
        user = request.user

        like_obj, created = Like.objects.get_or_create(photo=photo, user=user)
        if not created:
            like_obj.delete()
            liked = False
        else:
            liked = True

        return JsonResponse({
            "liked": liked,
            "likes_count": photo.likes.count(),
        })


# blog/views.py
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction

from .models import Blog
from .forms import BlogForm

class EditBlogView(LoginRequiredMixin, View):
    login_url = "login"

    def get(self, request, blog_id, *args, **kwargs):
        blog = get_object_or_404(Blog, id=blog_id)
        if blog.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Vous n'avez pas la permission d'éditer ce billet.")
        edit_form = BlogForm(instance=blog)
        context = {
            "edit_form": edit_form,
            "blog": blog,
        }
        return render(request, "blog/edit_blog.html", context)

    def post(self, request, blog_id, *args, **kwargs):
        blog = get_object_or_404(Blog, id=blog_id)
        if blog.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Vous ne pouvez pas modifier ou supprimer ce billet.")

        # --- Suppression ---
        if "delete_blog" in request.POST:
            try:
                with transaction.atomic():
                    if getattr(blog, "photo", None):
                        try:
                            blog.photo.delete()  # supprime fichier et instance Photo
                        except Exception as e:
                            print("Erreur suppression fichier photo:", e)
                    blog.delete()
                messages.success(request, "Billet supprimé.")
                return redirect("home")
            except Exception as e:
                print("Erreur suppression blog:", e)
                messages.error(request, "Impossible de supprimer le billet.")
                return redirect("home")

        # --- Edition ---
        elif "edit_blog" in request.POST:
            edit_form = BlogForm(request.POST, instance=blog)
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, "Billet mis à jour.")
                return redirect("home")
            else:
                print("Edit form errors:", edit_form.errors)
        else:
            # Aucun bouton valide pressé
            messages.error(request, "Action non reconnue.")
            edit_form = BlogForm(instance=blog)

        context = {
            "edit_form": edit_form,
            "blog": blog,
        }
        return render(request, "blog/edit_blog.html", context)