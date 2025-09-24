# blog/views.py
import re
from collections import Counter

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import CreateView, ListView, View, DetailView, FormView
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.contrib import messages
from django.forms import modelformset_factory
from django.contrib.auth import get_user_model
from django.db.models import Count

from . import forms, models
from .models import Photo, Blog, Like
from .forms import BlogForm, PhotoForm, FollowUsersForm
from .algorithme import compute_feed_for_user  # adapte si le module s'appelle autrement

User = get_user_model()

# ---------------------------
# Utilitaires d'extraction simple de tags
# ---------------------------
STOPWORDS = {
    'de','la','le','les','des','du','et','en','un','une','pour','sur','avec',
    'au','aux','par','se','sa','son','ses','que','qui','dans','ce','ces','comme'
}

def auto_extract_tags(text, max_tags=5):
    """
    Extraction simple de mots-clés depuis un texte :
    - garde les mots (lettres/chiffres),
    - met en minuscule,
    - filtre les stopwords,
    - renvoie les mots les plus fréquents (max_tags).
    """
    if not text:
        return []
    words = re.findall(r'\w+', text.lower(), flags=re.UNICODE)
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    if not words:
        return []
    common = [w for w, _ in Counter(words).most_common(max_tags)]
    return common

# ======================================================
# Page d'accueil
# ======================================================
# blog/views.py
from django.views.generic import ListView
from django.http import JsonResponse
from django.db.models import Count

from . import models
from .algorithme import compute_feed_for_user  # adapte le chemin si besoin


class HomeView(ListView):
    template_name = "blog/home.html"
    context_object_name = "photos"
    paginate_by = 20  # utile uniquement pour rendu HTML initial

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            # visiteurs → quelques photos récentes
            return list(
                models.Photo.objects
                .annotate(likes_count=Count('likes'))
                .order_by('-date_created')[:100]
            )
        # utilisateurs → feed personnalisé
        return compute_feed_for_user(user, limit=500)

    def _is_json_request(self):
        """Détecte si c’est une requête AJAX/JSON/scroll."""
        r = self.request
        if r.headers.get("x-requested-with") == "XMLHttpRequest":
            return True
        if "application/json" in r.headers.get("accept", ""):
            return True
        if "offset" in r.GET:  # utilisé par scroll infini
            return True
        return False

    def get(self, request, *args, **kwargs):
        """Renvoie JSON si c’est un scroll, sinon HTML classique."""
        if self._is_json_request():
            # pagination côté front
            try:
                offset = int(request.GET.get("offset", 0))
            except (TypeError, ValueError):
                offset = 0
            try:
                limit = int(request.GET.get("limit", 20))
            except (TypeError, ValueError):
                limit = 20

            feed = self.get_queryset()
            total = len(feed)

            start = max(0, offset)
            end = min(total, start + limit)
            batch = feed[start:end]

            # likes de l’utilisateur
            photo_likes = {}
            user = request.user
            if user.is_authenticated:
                liked_qs = (
                    models.Like.objects.filter(user=user, photo__in=batch)
                    .values_list("photo_id", flat=True)
                )
                photo_likes = {pid: True for pid in liked_qs}

            # transformer les objets en JSON safe
            items = []
            for photo in batch:
                uploader = getattr(photo, "uploader", None)
                uploader_info = {
                    "id": getattr(uploader, "id", None),
                    "username": getattr(uploader, "username", ""),
                    "profile_photo": getattr(
                        getattr(uploader, "profile_photo", None), "url", None
                    ),
                    "role": getattr(uploader, "role", None),
                } if uploader else {}

                items.append({
                    "id": photo.id,
                    "url": getattr(getattr(photo, "image", None), "url", None),
                    "caption": getattr(photo, "caption", ""),
                    "uploader": uploader_info,
                    "likes_count": getattr(photo, "likes_count", photo.likes.count()),
                    "liked": bool(photo_likes.get(photo.id, False)),
                    "date_created": photo.date_created.isoformat() if getattr(photo, "date_created", None) else None,
                })

            return JsonResponse({
                "photos": items,
                "offset": start,
                "limit": limit,
                "returned": len(items),
                "has_next": end < total,
                "total": total,
            })

        # rendu HTML normal
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Prépare le contexte pour le rendu HTML initial."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        photo_likes = {}

        if user.is_authenticated:
            liked_qs = models.Like.objects.filter(
                user=user, photo__in=context.get("photos", [])
            ).values_list("photo_id", flat=True)
            photo_likes = {pid: True for pid in liked_qs}

        context["photo_likes"] = photo_likes
        return context
        
        
# ======================================================
# Détail d'un blog
# ======================================================
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

        # exposer les tags (sécurisé)
        try:
            context["blog_tags"] = list(self.object.tags.all())
        except Exception:
            context["blog_tags"] = []

        try:
            context["photo_tags"] = list(photo.tags.all()) if photo else []
        except Exception:
            context["photo_tags"] = []

        return context

# ======================================================
# Upload de photo simple (avec tags + auto-extract)
# ======================================================
class PhotoUploadView(LoginRequiredMixin, CreateView):
    model = Photo
    form_class = PhotoForm
    template_name = "blog/photo_upload.html"
    success_url = reverse_lazy("home")
    login_url = "login"

    def form_valid(self, form):
        form.instance.uploader = self.request.user
        # sauvegarde l'instance
        response = super().form_valid(form)

        # sauvegarder les M2M (tags) si fournis via form
        try:
            form.save_m2m()
        except Exception:
            pass

        # si le template a fourni un champ 'tags' (input texte), on l'applique et on priorise cela
        tags_str = self.request.POST.get('tags', '').strip()
        if tags_str:
            tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
            try:
                self.object.tags.set(tags_list)
            except Exception:
                pass
        else:
            # sinon, auto-génération si aucun tag présent
            try:
                if not list(self.object.tags.all()):
                    generated = auto_extract_tags(form.cleaned_data.get('caption', '') or '')
                    if generated:
                        self.object.tags.add(*generated)
            except Exception:
                pass

        messages.success(self.request, "Photo téléchargée avec succès.")
        return response

# ======================================================
# Upload multiple photos (support tags par photo)
# ======================================================
class CreateMultiplePhotosView(LoginRequiredMixin, View):
    template_name = "blog/create_multiple_photos.html"
    success_url = "home"

    def get(self, request, *args, **kwargs):
        PhotoFormSet = modelformset_factory(Photo, form=PhotoForm, extra=5, can_delete=False)
        formset = PhotoFormSet(queryset=Photo.objects.none())
        return render(request, self.template_name, {"formset": formset})

    def post(self, request, *args, **kwargs):
        PhotoFormSet = modelformset_factory(Photo, form=PhotoForm, extra=5, can_delete=False)
        formset = PhotoFormSet(request.POST, request.FILES, queryset=Photo.objects.none())

        if formset.is_valid():
            for i, form in enumerate(formset):
                if form.cleaned_data:
                    photo = form.save(commit=False)
                    photo.uploader = request.user
                    photo.save()

                    # enregistrer M2M si le form contient tags field
                    try:
                        form.save_m2m()
                    except Exception:
                        pass

                    # récupérer tags spécifiques à ce form (input name="tags_0", "tags_1", ...)
                    tags_str = request.POST.get(f'tags_{i}', '').strip()
                    if tags_str:
                        tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                        try:
                            photo.tags.set(tags_list)
                        except Exception:
                            pass
                    else:
                        # auto-tags si vide
                        try:
                            if not list(photo.tags.all()):
                                caption = form.cleaned_data.get('caption', '') or ''
                                generated = auto_extract_tags(caption)
                                if generated:
                                    photo.tags.add(*generated)
                        except Exception:
                            pass

            messages.success(request, "Photos publiées avec succès.")
            return redirect(self.success_url)

        # si erreurs, on réaffiche le formulaire
        return render(request, self.template_name, {"formset": formset})

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
# Création blog + photo (permission add_blog)
# ======================================================
class BlogAndPhotoUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    login_url = "login"
    permission_required = "blog.add_blog"
    raise_exception = True

    def get(self, request, *args, **kwargs):
        return render(request, "blog/create_blog_post.html", {
            "blog_form": BlogForm(),
            "photo_form": PhotoForm(),
        })

    def post(self, request, *args, **kwargs):
        blog_form = BlogForm(request.POST)
        photo_form = PhotoForm(request.POST, request.FILES)

        if blog_form.is_valid() and photo_form.is_valid():
            try:
                with transaction.atomic():
                    # save photo first
                    photo = photo_form.save(commit=False)
                    photo.uploader = request.user
                    photo.save()
                    try:
                        photo_form.save_m2m()
                    except Exception:
                        pass

                    # save blog
                    blog = blog_form.save(commit=False)
                    blog.author = request.user
                    blog.photo = photo
                    blog.save()
                    try:
                        blog_form.save_m2m()
                    except Exception:
                        pass

                    # If the form provided a single 'tags' input (combined), apply to both photo and blog.
                    tags_str = request.POST.get('tags', '').strip()
                    if tags_str:
                        tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                        try:
                            photo.tags.set(tags_list)
                        except Exception:
                            pass
                        try:
                            blog.tags.set(tags_list)
                        except Exception:
                            pass

                    # auto-tags fallbacks
                    try:
                        if not list(photo.tags.all()):
                            generated = auto_extract_tags(photo.caption or '')
                            if generated:
                                photo.tags.add(*generated)
                    except Exception:
                        pass

                    try:
                        if not list(blog.tags.all()):
                            text_source = ((blog.title or '') + ' ' + (blog.content or '')).strip()
                            generated = auto_extract_tags(text_source)
                            if generated:
                                blog.tags.add(*generated)
                    except Exception:
                        pass

                messages.success(request, "Billet publié avec succès.")
                return redirect("home")
            except Exception as e:
                print("Erreur lors de la sauvegarde du billet :", e)
                messages.error(request, "Erreur lors de la publication. Réessaye.")

        # si invalid form, réafficher
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
        liked = created
        if not created:
            like_obj.delete()
            liked = False

        return JsonResponse({
            "liked": liked,
            "likes_count": photo.likes.count(),
        })

# ======================================================
# Edition / suppression blog
# ======================================================
class EditBlogView(LoginRequiredMixin, View):
    login_url = "login"

    def get(self, request, blog_id, *args, **kwargs):
        blog = get_object_or_404(Blog, id=blog_id)
        if blog.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Vous n'avez pas la permission d'éditer ce billet.")
        edit_form = BlogForm(instance=blog)
        return render(request, "blog/edit_blog.html", {"edit_form": edit_form, "blog": blog})

    def post(self, request, blog_id, *args, **kwargs):
        blog = get_object_or_404(Blog, id=blog_id)
        if blog.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Vous ne pouvez pas modifier ou supprimer ce billet.")

        if "delete_blog" in request.POST:
            try:
                with transaction.atomic():
                    if getattr(blog, "photo", None):
                        try:
                            blog.photo.delete()
                        except Exception as e:
                            print("Erreur suppression fichier photo:", e)
                    blog.delete()
                messages.success(request, "Billet supprimé.")
                return redirect("home")
            except Exception as e:
                print("Erreur suppression blog:", e)
                messages.error(request, "Impossible de supprimer le billet.")
                return redirect("home")

        elif "edit_blog" in request.POST:
            edit_form = BlogForm(request.POST, instance=blog)
            if edit_form.is_valid():
                blog = edit_form.save()
                try:
                    edit_form.save_m2m()
                except Exception:
                    pass

                # gérer tags si fournis via input 'tags' (pré-rempli dans template)
                tags_str = request.POST.get('tags', '').strip()
                if tags_str:
                    tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    try:
                        blog.tags.set(tags_list)
                    except Exception:
                        pass

                messages.success(request, "Billet mis à jour.")
                return redirect("home")
            else:
                print("Edit form errors:", edit_form.errors)
        else:
            messages.error(request, "Action non reconnue.")
            edit_form = BlogForm(instance=blog)

        return render(request, "blog/edit_blog.html", {"edit_form": edit_form, "blog": blog})

# ======================================================
# FollowUsersView
# ======================================================
class FollowUsersView(LoginRequiredMixin, FormView):
    template_name = "blog/follow_users_form.html"
    form_class = FollowUsersForm
    success_url = reverse_lazy('home')

    def get_form(self, form_class=None):
        return self.form_class(instance=self.request.user, **self.get_form_kwargs())

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)




from django.views.generic import ListView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from blog.models import Photo, Like

User = get_user_model()

class UserProfileView(ListView):
    template_name = 'blog/user_profile.html'
    context_object_name = 'photos'
    paginate_by = 20

    def get_queryset(self):
        self.profile_user = get_object_or_404(User, username=self.kwargs['username'])
        return Photo.objects.filter(uploader=self.profile_user).order_by('-date_created')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_user'] = self.profile_user
        context['photos_count'] = self.get_queryset().count()
        context['followers_count'] = self.profile_user.followers.count()
        context['likes_count'] = sum(photo.likes.count() for photo in self.get_queryset())

        # Dictionnaire pour savoir quelles photos l'utilisateur connecté a likées
        if self.request.user.is_authenticated:
            user_likes = Like.objects.filter(user=self.request.user, photo__in=self.get_queryset())
            context['photo_likes'] = {like.photo.id: True for like in user_likes}
        else:
            context['photo_likes'] = {}

        return context