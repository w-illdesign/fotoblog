from django.db.models import Count

def user_stats(request):
    if request.user.is_authenticated:
        user = request.user
        followers_count = user.followers.count()
        photos_count = user.photo_set.count()
        likes_count = sum(photo.likes.count() for photo in user.photo_set.all())
    else:
        followers_count = photos_count = likes_count = 0

    return {
        'followers_count': followers_count,
        'photos_count': photos_count,
        'likes_count': likes_count,
    }
    
    
    