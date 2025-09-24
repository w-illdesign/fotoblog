# Ajoute/replace dans blog/algorithms.py
from collections import Counter
from random import sample, shuffle
from datetime import timedelta
import math

from django.apps import apps
from django.db.models import Count
from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist

from . import models

# --- Hyperparamètres pour pourcentages (somme ≈ 100) ---
# Ajuste ces valeurs pour changer la probabilité d'apparition de chaque type.
BUCKET_PERCENTAGES = {
    'followed': 35,        # contenus d'utilisateurs suivis
    'ultra_new': 15,       # uploads très récents (early exposure)
    'popular': 15,         # contenus très likés
    'creator_discovery': 10, # créateurs non-followed
    'blogs': 10,           # contenus type blog
    'random': 15,          # aléatoire depuis le reste
}

# Si tu veux, tu peux normaliser automatiquement pour que la somme fasse exactement 100.
def _normalize_percentages(d):
    total = sum(d.values())
    if total == 0:
        return d
    factor = 100.0 / total
    return {k: v * factor for k, v in d.items()}

# --- autres hyperparamètres (garde ceux que tu veux ajuster) ---
CANDIDATE_RECENT_DAYS = 30
CANDIDATE_TOP_LIKED = 200
CANDIDATE_MAX = 500
NEW_UPLOAD_WINDOW_HOURS = 48
NEW_EXPOSURE_PERCENT = 15
RECENT_LIKE_WINDOW_HOURS = 6
DISCOVERY_RATIO = 0.20
EXCLUDE_VIEWED_BY_DEFAULT = True
ALLOW_VIEWED_IF_INSUFFICIENT = True

# --- Fonction utilitaire: échantillonnage pondéré sans remise ---
def weighted_sample_no_replace(items, weights, k):
    """
    items: list
    weights: list of same length (non-negative)
    k: desired sample size
    Retourne up to k items sampled without replacement with probability proportionnelle aux weights.
    Se dégrade en sample() si toutes les weights==0.
    """
    assert len(items) == len(weights)
    if k <= 0 or not items:
        return []
    # si toutes les weights sont nulles, on fait un sample aléatoire simple
    if all(w == 0 or w is None for w in weights):
        try:
            return sample(items, min(k, len(items)))
        except ValueError:
            return items[:min(k, len(items))]
    pool = list(zip(items, weights))
    chosen = []
    # algorithme simple: itérer k fois, normaliser et choisir proportionnellement
    for _ in range(min(k, len(pool))):
        total = sum(w for (_, w) in pool if w > 0)
        if total <= 0:
            # finish with uniform sample
            remaining = [it for it, _ in pool]
            try:
                s = sample(remaining, min(k - len(chosen), len(remaining)))
            except ValueError:
                s = remaining[:min(k - len(chosen), len(remaining))]
            chosen.extend(s)
            break
        r = math.fsum([w for (_, w) in pool]) * 0.0  # avoid lint warning
        # cumulate and pick
        import random
        pick = random.random() * total
        acc = 0.0
        for i, (it, w) in enumerate(pool):
            if w <= 0:
                continue
            acc += w
            if pick <= acc:
                chosen.append(it)
                pool.pop(i)
                break
    return chosen

# --- Fonction principale (version probabiliste par buckets) ---
def compute_feed_for_user(user, limit=20):
    now = timezone.now()
    pct = _normalize_percentages(BUCKET_PERCENTAGES)

    # --- Construire pool photo comme précédemment (avec tags si présents) ---
    base_photo_qs = models.Photo.objects.select_related('uploader').annotate(likes_count=Count('likes'))
    try:
        models.Photo._meta.get_field('tags')
        recent_photo_qs = base_photo_qs.filter(date_created__gte=now - timedelta(days=CANDIDATE_RECENT_DAYS)).prefetch_related('tags')
        top_liked_photo_qs = base_photo_qs.order_by('-likes_count')[:CANDIDATE_TOP_LIKED].prefetch_related('tags')
    except FieldDoesNotExist:
        recent_photo_qs = base_photo_qs.filter(date_created__gte=now - timedelta(days=CANDIDATE_RECENT_DAYS))
        top_liked_photo_qs = base_photo_qs.order_by('-likes_count')[:CANDIDATE_TOP_LIKED]

    ultra_new_cutoff = now - timedelta(hours=NEW_UPLOAD_WINDOW_HOURS)
    try:
        ultra_new_photo_qs = base_photo_qs.filter(date_created__gte=ultra_new_cutoff).order_by('-date_created')
    except Exception:
        ultra_new_photo_qs = base_photo_qs.filter(date_created__gte=ultra_new_cutoff)

    # --- Blogs (si disponibles) ---
    recent_blog_qs = []
    top_blog_qs = []
    ultra_new_blog_qs = []
    try:
        Blog = apps.get_model('blog', 'Blog')
        try:
            base_blog_qs = Blog.objects.select_related('author').annotate(likes_count=Count('likes'))
        except Exception:
            base_blog_qs = Blog.objects.select_related('author')
        recent_blog_qs = base_blog_qs.filter(date_created__gte=now - timedelta(days=CANDIDATE_RECENT_DAYS))
        top_blog_qs = base_blog_qs.order_by('-date_created')[:CANDIDATE_TOP_LIKED]
        ultra_new_blog_qs = base_blog_qs.filter(date_created__gte=ultra_new_cutoff).order_by('-date_created')
    except LookupError:
        pass

    # --- Construire un pool mixte limité ---
    candidate_map = {}
    def _add(kind, obj):
        key = (kind, obj.id)
        if key not in candidate_map and len(candidate_map) < CANDIDATE_MAX:
            candidate_map[key] = {
                'kind': kind,
                'obj': obj,
                'uploader_id': getattr(obj, 'uploader_id', getattr(obj, 'author_id', None)),
                'date_created': getattr(obj, 'date_created', None),
                'likes_count': getattr(obj, 'likes_count', 0),
            }

    for p in list(ultra_new_photo_qs) + list(recent_photo_qs) + list(top_liked_photo_qs):
        _add('photo', p)
    for b in list(ultra_new_blog_qs) + list(recent_blog_qs) + list(top_blog_qs):
        _add('blog', b)

    all_candidates = list(candidate_map.values())
    if not all_candidates:
        # fallback comme avant
        return list(models.Photo.objects.annotate(likes_count=Count('likes')).order_by('-date_created')[:limit])

    # --- Pré-calculs uploader/author pour filtrages et scores simples ---
    uploader_ids = {c['uploader_id'] for c in all_candidates if c['uploader_id'] is not None}
    likes_per_uploader = {}
    photos_per_uploader = {}
    blogs_per_uploader = {}
    recent_posts = {}
    if uploader_ids:
        try:
            likes_qs = models.Like.objects.filter(photo__uploader_id__in=uploader_ids).values('photo__uploader_id').annotate(total_likes=Count('id'))
            likes_per_uploader = {it['photo__uploader_id']: it['total_likes'] for it in likes_qs}
        except Exception:
            likes_per_uploader = {}
        try:
            pp = models.Photo.objects.filter(uploader_id__in=uploader_ids).values('uploader_id').annotate(photo_count=Count('id'))
            photos_per_uploader = {it['uploader_id']: it['photo_count'] for it in pp}
        except Exception:
            photos_per_uploader = {}
        try:
            bb = models.Blog.objects.filter(author_id__in=uploader_ids).values('author_id').annotate(blog_count=Count('id'))
            blogs_per_uploader = {it['author_id']: it['blog_count'] for it in bb}
        except Exception:
            blogs_per_uploader = {}
        recent_cutoff_global = now - timedelta(days=30)
        try:
            rp = models.Photo.objects.filter(uploader_id__in=uploader_ids, date_created__gte=recent_cutoff_global).values('uploader_id').annotate(count=Count('id'))
            for it in rp:
                recent_posts[it['uploader_id']] = it['count']
            rb = models.Blog.objects.filter(author_id__in=uploader_ids, date_created__gte=recent_cutoff_global).values('author_id').annotate(count=Count('id'))
            for it in rb:
                recent_posts[it['author_id']] = recent_posts.get(it['author_id'], 0) + it['count']
        except Exception:
            pass

    uploader_stats = {}
    for uid in uploader_ids:
        total_likes = likes_per_uploader.get(uid, 0)
        total_photos = photos_per_uploader.get(uid, 0)
        total_blogs = blogs_per_uploader.get(uid, 0)
        recent_count = recent_posts.get(uid, 0)
        is_creator = total_blogs > 0
        like_score = total_likes / (total_photos + 1)
        activity_score = min(recent_count / 10.0, 1.0)
        influence_score = like_score * 10.0 + activity_score * 20.0
        uploader_stats[uid] = {
            'is_creator': is_creator,
            'influence_score': influence_score
        }

    # --- Profil utilisateur: follows, likes, vues ---
    followed_user_ids = set()
    user_liked_photo_ids = set()
    user_liked_blog_ids = set()
    viewed_items = set()
    if user and user.is_authenticated:
        try:
            followed_user_ids = set(user.follows.values_list('id', flat=True))
        except Exception:
            followed_user_ids = set()
        try:
            user_liked_photo_ids = set(models.Like.objects.filter(user=user).values_list('photo_id', flat=True))
        except Exception:
            user_liked_photo_ids = set()
        try:
            BlogLike = apps.get_model('blog', 'BlogLike')
            user_liked_blog_ids = set(BlogLike.objects.filter(user=user).values_list('blog_id', flat=True))
        except Exception:
            user_liked_blog_ids = set()
        try:
            PhotoView = apps.get_model('blog', 'PhotoView')
            for pid in PhotoView.objects.filter(user=user).values_list('photo_id', flat=True):
                viewed_items.add(('photo', pid))
        except Exception:
            pass
        try:
            BlogView = apps.get_model('blog', 'BlogView')
            for bid in BlogView.objects.filter(user=user).values_list('blog_id', flat=True):
                viewed_items.add(('blog', bid))
        except Exception:
            pass

    # --- Construire pools selon buckets ---
    pools = {
        'followed': [],
        'ultra_new': [],
        'popular': [],
        'creator_discovery': [],
        'blogs': [],
        'random': []
    }

    # helper pour déterminer ultra_new / popular etc.
    for c in all_candidates:
        kind = c['kind']
        obj = c['obj']
        uid = c['uploader_id']
        # is followed?
        if uid in followed_user_ids:
            pools['followed'].append(c)
        # ultra new (recent)
        try:
            if c['date_created'] and (now - c['date_created']).total_seconds() <= NEW_UPLOAD_WINDOW_HOURS * 3600:
                pools['ultra_new'].append(c)
        except Exception:
            pass
        # popular (by likes_count)
        try:
            if (c.get('likes_count') or 0) >= 10:  # seuil simple, ajuste-le
                pools['popular'].append(c)
        except Exception:
            pass
        # creator non followed
        if uid not in followed_user_ids and uploader_stats.get(uid, {}).get('is_creator', False):
            pools['creator_discovery'].append(c)
        # blogs
        if kind == 'blog':
            pools['blogs'].append(c)
        # random pool will include everything; we'll filter later
        pools['random'].append(c)

    # --- Calculer le nombre d'items à prendre par bucket (arrondi) ---
    desired_counts = {}
    remaining_slots = limit
    # compute raw counts
    for k, p in pct.items():
        desired_counts[k] = int(round(limit * (p / 100.0)))
    # adjust sum to be exactly limit (simple redistribution)
    s = sum(desired_counts.values())
    if s != limit:
        diff = limit - s
        # add/subtract 1 to/from largest bucket(s) until fixed
        keys_sorted = sorted(desired_counts.items(), key=lambda x: -x[1])
        i = 0
        while diff != 0:
            key = keys_sorted[i % len(keys_sorted)][0]
            if diff > 0:
                desired_counts[key] += 1
                diff -= 1
            else:
                if desired_counts[key] > 0:
                    desired_counts[key] -= 1
                    diff += 1
            i += 1

    # --- Sélection par bucket (d'abord essayer de prendre items non-vus) ---
    selected = []
    selected_keys = set()

    def take_from_pool(pool, need):
        """
        Prend jusqu'à `need` items depuis pool en priorisant non-vus, puis vus si autorisé.
        Pool = list of candidate dicts.
        """
        nonlocal selected, selected_keys
        if not pool or need <= 0:
            return []
        # prefer non-vus
        non_viewed = [c for c in pool if (c['kind'], c['obj'].id) not in viewed_items and (c['kind'], c['obj'].id) not in selected_keys]
        viewed = [c for c in pool if (c['kind'], c['obj'].id) in viewed_items and (c['kind'], c['obj'].id) not in selected_keys]
        picked = []
        # random pick from non_viewed
        try:
            cnt = min(len(non_viewed), need)
            if cnt > 0:
                # sample uniformly; could be replaced by weighted_sample_no_replace using influence or likes
                sampled = sample(non_viewed, cnt)
                picked.extend(sampled)
        except ValueError:
            sampled = non_viewed[:min(len(non_viewed), need)]
            picked.extend(sampled)
        if len(picked) < need and ALLOW_VIEWED_IF_INSUFFICIENT:
            need2 = need - len(picked)
            try:
                cnt2 = min(len(viewed), need2)
                if cnt2 > 0:
                    sampled2 = sample(viewed, cnt2)
                    picked.extend(sampled2)
            except ValueError:
                picked.extend(viewed[:min(len(viewed), need2)])
        # mark selected
        for c in picked:
            selected.append(c)
            selected_keys.add((c['kind'], c['obj'].id))
        return picked

    # iterate buckets in order of importance to prefer followed first, etc.
    bucket_priority = ['followed', 'ultra_new', 'popular', 'creator_discovery', 'blogs', 'random']
    for b in bucket_priority:
        need = desired_counts.get(b, 0)
        pool = pools.get(b, [])
        take_from_pool(pool, need)

    # --- if we didn't reach limit, fill from remaining non-selected non-viewed, then viewed if allowed ---
    if len(selected) < limit:
        remaining_needed = limit - len(selected)
        remaining_candidates = [c for c in all_candidates if (c['kind'], c['obj'].id) not in selected_keys]
        # prefer non-viewed first
        non_viewed_rem = [c for c in remaining_candidates if (c['kind'], c['obj'].id) not in viewed_items]
        try:
            add = sample(non_viewed_rem, min(remaining_needed, len(non_viewed_rem)))
        except ValueError:
            add = non_viewed_rem[:min(remaining_needed, len(non_viewed_rem))]
        for c in add:
            selected.append(c); selected_keys.add((c['kind'], c['obj'].id))
        remaining_needed = limit - len(selected)
        if remaining_needed > 0 and ALLOW_VIEWED_IF_INSUFFICIENT:
            viewed_rem = [c for c in remaining_candidates if (c['kind'], c['obj'].id) in viewed_items]
            try:
                add2 = sample(viewed_rem, min(remaining_needed, len(viewed_rem)))
            except ValueError:
                add2 = viewed_rem[:min(remaining_needed, len(viewed_rem))]
            for c in add2:
                selected.append(c); selected_keys.add((c['kind'], c['obj'].id))

    # --- Mélange final pour donner l'aspect aléatoire demandé ---
    shuffle(selected)

    # --- Retourner les instances (Photo/Blog) ---
    return [c['obj'] for c in selected[:limit]]