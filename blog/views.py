# blog/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView, View, DetailView
from django.http import JsonResponse

from . import forms
from .models import Photo, Blog, Like  # On suppose que Like est dans models.py


# -------------------------
# Page d'accueil
# -------------------------
# blog/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from .models import Photo, Blog

class HomeView(LoginRequiredMixin, ListView):
    model = Photo
    template_name = "blog/home.html"
    context_object_name = "photos"
    ordering = ["-id"]
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile_photo"] = self.request.user.profile_photo

        # Dictionnaire photo_id -> bool (si l'utilisateur a liké)
        user = self.request.user
        photo_likes = {}
        for photo in context["photos"]:
            photo_likes[photo.id] = photo.likes.filter(user=user).exists()
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
        photo = self.object.photo
        # Si la photo existe, on vérifie si l'utilisateur a liké
        context["user_liked"] = photo.likes.filter(user=user).exists() if photo else False
        context["likes_count"] = photo.likes.count() if photo else 0
        context["profile_photo"] = user.profile_photo
        return context


# -------------------------
# Upload de photo simple
# -------------------------
class PhotoUploadView(LoginRequiredMixin, CreateView):
    model = Photo
    form_class = forms.PhotoForm
    template_name = "blog/photo_upload.html"
    success_url = reverse_lazy("home")
    login_url = "login"

    def form_valid(self, form):
        form.instance.uploader = self.request.user
        return super().form_valid(form)


# -------------------------
# Mise à jour photo profil
# -------------------------
class UpdateProfilePhotoView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request, *args, **kwargs):
        photo = request.FILES.get("profile_photo")
        if photo:
            request.user.profile_photo = photo
            request.user.save()
        return redirect("home")


# -------------------------
# Création blog + photo
# -------------------------
class BlogAndPhotoUploadView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, *args, **kwargs):
        blog_form = forms.BlogForm()
        photo_form = forms.PhotoForm()
        return render(request, 'blog/create_blog_post.html', {
            'blog_form': blog_form,
            'photo_form': photo_form
        })

    def post(self, request, *args, **kwargs):
        blog_form = forms.BlogForm(request.POST)
        photo_form = forms.PhotoForm(request.POST, request.FILES)

        if all([blog_form.is_valid(), photo_form.is_valid()]):
            # Sauvegarde photo
            photo = photo_form.save(commit=False)
            photo.uploader = request.user
            photo.save()

            # Sauvegarde blog
            blog = blog_form.save(commit=False)
            blog.author = request.user
            blog.photo = photo
            blog.save()

            return redirect('home')

        return render(request, 'blog/create_blog_post.html', {
            'blog_form': blog_form,
            'photo_form': photo_form
        })



# -------------------------
# Like / Unlike AJAX
# -------------------------



class ToggleLikeView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request, *args, **kwargs):
        # Récupère l'id soit depuis l'URL (kwargs) soit depuis le body POST (fallback)
        photo_id = kwargs.get('photo_id') or request.POST.get('photo_id')
        if not photo_id:
            return JsonResponse({'error': 'photo_id manquant'}, status=400)

        photo = get_object_or_404(Photo, id=photo_id)
        user = request.user

        like_obj, created = Like.objects.get_or_create(photo=photo, user=user)
        if not created:
            like_obj.delete()
            liked = False
        else:
            liked = True

        return JsonResponse({
            'liked': liked,
            'likes_count': photo.likes.count()
        })