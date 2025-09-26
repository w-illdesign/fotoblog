# blog/views.py
import re
from collections import Counter

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse, NoReverseMatch
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
from .algorithme import compute_feed_for_user  
from blog.utils import publications_time 

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

class HomeView(ListView):
    template_name = "blog/home.html"
    context_object_name = "photos"
    paginate_by = 20

    def _normalize_feed(self, feed):
        """
        Normalise le feed en LISTE d'instances Photo.
        Accepté : QuerySet[Photo], list[Photo], list[int], list[dict {'id':...}], mixte.
        Retourne : list[Photo] (ordre préservé quand possible).
        """
        if feed is None:
            return []

        try:
            iter(feed)
        except TypeError:
            return []

        ids = []
        instances = []
        for item in feed:
            # instance Photo déjà fournie
            if isinstance(item, Photo):
                instances.append(item)
                ids.append(item.id)
                continue

            # dict contenant un id
            if isinstance(item, dict) and "id" in item:
                try:
                    ids.append(int(item.get("id")))
                except Exception:
                    pass
                continue

            # entier (id)
            if isinstance(item, int):
                ids.append(item)
                continue

            # objet quelconque avec attribut id
            pid = getattr(item, "id", None)
            if isinstance(pid, int):
                ids.append(pid)
                continue

        # si on a seulement des instances Photo, on les retourne directement
        if not ids and instances:
            return instances
        if not ids:
            return []

        # récupérer les instances en base (select_related uploader pour éviter N+1)
        qs_photos = Photo.objects.filter(id__in=ids).select_related("uploader")
        photos_map = {p.id: p for p in qs_photos}

        normalized = []
        seen = set()
        for pid in ids:
            obj = photos_map.get(pid)
            if obj and obj.id not in seen:
                normalized.append(obj)
                seen.add(obj.id)

        # ajouter les instances originales si présentes et non déjà ajoutées
        for p in instances:
            if p.id not in seen:
                normalized.append(p)
                seen.add(p.id)

        return normalized

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            # visiteurs -> photos récentes (QuerySet slice, avec annotation likes_count utile côté serveur)
            return Photo.objects.annotate(likes_count=Count("likes")).order_by("-date_created")[:100]

        # utilisateur connecté -> feed personnalisé (normalize to Photo instances)
        feed = compute_feed_for_user(user, limit=500)
        return self._normalize_feed(feed)

    def _is_json_request(self):
        r = self.request
        return (
            r.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in r.headers.get("accept", "")
            or "offset" in r.GET
        )

    def get(self, request, *args, **kwargs):
        # branche AJAX / JSON (infinite scroll)
        if self._is_json_request():
            try:
                offset = int(request.GET.get("offset", 0))
            except (TypeError, ValueError):
                offset = 0
            try:
                limit = int(request.GET.get("limit", 20))
            except (TypeError, ValueError):
                limit = 20

            feed = self.get_queryset()
            feed_list = list(feed) if hasattr(feed, "__iter__") else []
            total = len(feed_list)

            start = max(0, offset)
            end = min(total, start + limit)
            batch = feed_list[start:end]

            # ids valides du batch
            photo_ids = [getattr(p, "id", None) for p in batch if getattr(p, "id", None) is not None]

            # likes de l'utilisateur pour ces photos
            photo_likes = {}
            user = request.user
            if user.is_authenticated and photo_ids:
                liked_qs = Like.objects.filter(user=user, photo_id__in=photo_ids).values_list("photo_id", flat=True)
                photo_likes = {int(pid): True for pid in liked_qs}

            # construire la réponse JSON (sécurisée / sérialisable)
            items = []
            for raw in batch:
                # s'assurer d'avoir une instance Photo
                photo = raw
                if not isinstance(photo, Photo):
                    # tenter de récupérer depuis la base si on a juste un id/dict
                    pid = None
                    if isinstance(raw, dict):
                        pid = raw.get("id")
                    else:
                        pid = getattr(raw, "id", None)
                    if pid:
                        try:
                            photo = Photo.objects.select_related("uploader").get(id=pid)
                        except Photo.DoesNotExist:
                            continue
                    else:
                        continue

                uploader = getattr(photo, "uploader", None)

                # profile_photo url (sécurisé) — évite ValueError si pas de fichier
                profile_photo_url = None
                if uploader:
                    pp = getattr(uploader, "profile_photo", None)
                    if pp and getattr(pp, "name", ""):
                        try:
                            profile_photo_url = pp.url
                        except Exception:
                            profile_photo_url = None

                # -------- safe likes_count --------
                likes_count = 0
                try:
                    lc = getattr(photo, "likes_count", None)
                    if callable(lc):
                        try:
                            val = lc()
                            likes_count = int(val) if val is not None else 0
                        except Exception:
                            likes_count = 0
                    elif lc is not None:
                        try:
                            likes_count = int(lc)
                        except Exception:
                            likes_count = 0
                    else:
                        try:
                            likes_count = int(photo.likes.count())
                        except Exception:
                            likes_count = 0
                except Exception:
                    likes_count = 0
                # -----------------------------------

                # date iso
                date_created_iso = None
                dc = getattr(photo, "date_created", None)
                if dc:
                    try:
                        date_created_iso = dc.isoformat()
                    except Exception:
                        date_created_iso = str(dc)

                liked_flag = bool(photo_likes.get(int(photo.id), False))

                # uploader info (JSON-safe) + profile_url via reverse() avec fallback
                uploader_info = {}
                if uploader:
                    username = getattr(uploader, "username", "") or ""
                    try:
                        profile_url = reverse("user-profile", kwargs={"username": username})
                    except NoReverseMatch:
                        profile_url = f"/profile/{username}/"
                    uploader_info = {
                        "id": int(getattr(uploader, "id")) if getattr(uploader, "id", None) is not None else None,
                        "username": str(username),
                        "profile_photo": profile_photo_url,
                        "role": str(getattr(uploader, "role", "")) or "",
                        "profile_url": profile_url,
                    }

                # date_facebook pré-calculée (sécurisé)
                try:
                    date_fb = publications_time(getattr(photo, "date_created", None))
                except Exception:
                    date_fb = ""

                items.append({
                    "id": int(photo.id),
                    "url": str(getattr(getattr(photo, "image", None), "url", "")) or None,
                    "caption": str(getattr(photo, "caption", "")) or "",
                    "uploader": uploader_info,
                    "likes_count": likes_count,
                    "liked": bool(liked_flag),
                    "date_created": date_created_iso,
                    "date_facebook": date_fb,
                })

            return JsonResponse({
                "photos": items,
                "offset": start,
                "limit": limit,
                "returned": len(items),
                "has_next": end < total,
                "total": total,
            })

        # rendu HTML normal (ListView)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Construit le contexte pour le rendu HTML initial (photos, photo_likes,
        photo_dates_facebook, et ajout d'un profile_url sur chaque uploader).
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user

        photos_seq = context.get("photos", [])
        photos_list = list(photos_seq) if hasattr(photos_seq, "__iter__") else []

        # ids valides
        photo_ids = [getattr(p, "id", None) for p in photos_list if getattr(p, "id", None) is not None]

        # likes de l’utilisateur (pour les photos rendues côté serveur)
        photo_likes = {}
        if user.is_authenticated and photo_ids:
            liked_qs = Like.objects.filter(user=user, photo_id__in=photo_ids).values_list("photo_id", flat=True)
            photo_likes = {int(pid): True for pid in liked_qs}
        context["photo_likes"] = photo_likes

        # préparer date_facebook pour affichage côté template
        photo_dates_facebook = {}
        for photo in photos_list:
            try:
                photo_dates_facebook[photo.id] = publications_time(photo.date_created)
            except Exception:
                photo_dates_facebook[photo.id] = ""
        context["photo_dates_facebook"] = photo_dates_facebook

        # ajouter profile_url sur uploader pour faciliter le template server-side
        for photo in photos_list:
            uploader = getattr(photo, "uploader", None)
            if uploader:
                try:
                    username = getattr(uploader, "username", "") or ""
                    try:
                        uploader.profile_url = reverse("user-profile", kwargs={"username": username})
                    except NoReverseMatch:
                        uploader.profile_url = f"/profile/{username}/"
                except Exception:
                    uploader.profile_url = None

        return context
        
# ======================================================
# Détail d'un blog
# ======================================================
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Blog, Photo, Like

class BlogDetailView(LoginRequiredMixin, DetailView):
    model = Blog
    template_name = "blog/view_blog.html"
    context_object_name = "blog"
    pk_url_kwarg = "blog_id"
    login_url = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        blog = self.object
        photo = getattr(blog, "photo", None)

        # Likes
        if photo:
            likes_count = photo.likes.count()
            user_liked = photo.likes.filter(user=user).exists() if user.is_authenticated else False
            context["photo_likes"] = {photo.id: user_liked}
        else:
            likes_count = 0
            context["photo_likes"] = {}

        context["likes_count"] = likes_count
        context["user_liked"] = photo.likes.filter(user=user).exists() if photo and user.is_authenticated else False

        # Exposer les tags de blog et photo
        try:
            context["blog_tags"] = list(blog.tags.all())
        except Exception:
            context["blog_tags"] = []

        try:
            context["photo_tags"] = list(photo.tags.all()) if photo else []
        except Exception:
            context["photo_tags"] = []

        # Photo de profil de l'utilisateur courant
        context["profile_photo"] = getattr(user, "profile_photo", None)

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

from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from django.db.models import Count
from django.http import JsonResponse

from .models import Photo, Like
from django.contrib.auth import get_user_model

User = get_user_model()

class UserProfileView(ListView):
    template_name = 'blog/user_profile.html'
    context_object_name = 'photos'
    paginate_by = 20

    def get_queryset(self):
        self.profile_user = get_object_or_404(User, username=self.kwargs['username'])
        # Annotation pour likes_count pour éviter de compter à chaque photo
        return Photo.objects.filter(uploader=self.profile_user).annotate(likes_count=Count('likes')).order_by('-date_created')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        photos_qs = self.get_queryset()
        context['profile_user'] = self.profile_user
        context['photos_count'] = photos_qs.count()
        try:
            context['followers_count'] = self.profile_user.followers.count()
        except Exception:
            context['followers_count'] = 0
        try:
            context['likes_count'] = sum(photo.likes_count for photo in photos_qs)
        except Exception:
            context['likes_count'] = 0

        # Dictionnaire photo_id -> liked par l'utilisateur connecté
        if self.request.user.is_authenticated:
            user_likes = Like.objects.filter(user=self.request.user, photo__in=photos_qs)
            context['photo_likes'] = {like.photo.id: True for like in user_likes}
        else:
            context['photo_likes'] = {}

        # Préparer la date_facebook si besoin (comme dans home.js)
        try:
            from .utils import publications_time
            context['photo_dates_facebook'] = {photo.id: publications_time(photo.date_created) for photo in photos_qs}
        except Exception:
            context['photo_dates_facebook'] = {photo.id: str(photo.date_created) for photo in photos_qs}

        return context

    def _is_json_request(self):
        r = self.request
        return (
            r.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in (r.headers.get('accept') or '')
            or 'offset' in r.GET
        )

    def get(self, request, *args, **kwargs):
        if self._is_json_request():
            offset = int(request.GET.get('offset', 0) or 0)
            limit = int(request.GET.get('limit', self.paginate_by) or self.paginate_by)
            feed_qs = self.get_queryset()
            feed_list = list(feed_qs)
            total = len(feed_list)
            batch = feed_list[offset:offset+limit]

            # likes de l'utilisateur courant
            photo_ids = [p.id for p in batch]
            photo_likes = {}
            if request.user.is_authenticated and photo_ids:
                liked_ids = Like.objects.filter(user=request.user, photo_id__in=photo_ids).values_list('photo_id', flat=True)
                photo_likes = {pid: True for pid in liked_ids}

            items = []
            for photo in batch:
                uploader = getattr(photo, 'uploader', None)
                profile_photo_url = getattr(getattr(uploader, 'profile_photo', None), 'url', '') if uploader else None
                try:
                    likes_count = int(getattr(photo, 'likes_count', photo.likes.count()))
                except Exception:
                    likes_count = 0
                liked_flag = bool(photo_likes.get(photo.id, False))
                # date_facebook si possible
                try:
                    from .utils import publications_time
                    date_fb = publications_time(photo.date_created)
                except Exception:
                    date_fb = str(photo.date_created)
                items.append({
                    'id': photo.id,
                    'url': getattr(getattr(photo, 'image', None), 'url', None),
                    'caption': photo.caption or '',
                    'uploader': {
                        'id': uploader.id if uploader else None,
                        'username': uploader.username if uploader else '',
                        'profile_photo': profile_photo_url,
                        'role': getattr(uploader, 'role', '') if uploader else '',
                        'profile_url': f'/profile/{uploader.username}/' if uploader else ''
                    },
                    'likes_count': likes_count,
                    'liked': liked_flag,
                    'date_created': photo.date_created.isoformat() if photo.date_created else None,
                    'date_facebook': date_fb
                })

            return JsonResponse({
                'photos': items,
                'offset': offset,
                'limit': limit,
                'returned': len(items),
                'has_next': offset + limit < total,
                'total': total
            })

        return super().get(request, *args, **kwargs)