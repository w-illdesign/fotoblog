# fotoblog/urls.py
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Auth views
from authentification.views import LoginPageView, LogoutUserView, SignupPageView

# Blog views (import explicite)
from blog.views import (
    HomeView,
    PhotoUploadView,
    UpdateProfilePhotoView,
    BlogAndPhotoUploadView,
    BlogDetailView,
    ToggleLikeView, 
    EditBlogView,  
    CreateMultiplePhotosView,
    FollowUsersView,
    UserProfileView,
)



urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('login', LoginPageView.as_view(), name='login'),
    path('logout/', LogoutUserView.as_view(), name='logout'),
    path('signup/', SignupPageView.as_view(), name='signup'),

    # Blog
    path('', HomeView.as_view(), name='home'),
    path('photo/upload/', PhotoUploadView.as_view(), name='photo_upload'),
    path('update-profile-photo/', UpdateProfilePhotoView.as_view(), name='update_profile_photo'),
    path('create/', BlogAndPhotoUploadView.as_view(), name='create_blog_post'),
    path("photos/multiple/", CreateMultiplePhotosView.as_view(), name="create_multiple_photos"),

    # Blog detail
    path('blog/<int:blog_id>/', BlogDetailView.as_view(), name='view_blog'),

    # Toggle like
    path('photo/<int:photo_id>/like/', ToggleLikeView.as_view(), name='toggle_like'),

    # Edit blog
    path('blog/<int:blog_id>/edit/', EditBlogView.as_view(), name='edit_blog'),
    
    
   
    path('follow-users/', FollowUsersView.as_view(), name='follow_users'),
    
    
   
    path('profile/<str:username>/', UserProfileView.as_view(), name='user-profile'),

]





if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)