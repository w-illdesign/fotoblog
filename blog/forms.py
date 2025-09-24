# blog/forms.py
from django import forms
from . import models
from taggit.forms import TagWidget  # 👈 widget pour tags

class PhotoForm(forms.ModelForm):
    class Meta:
        model = models.Photo
        fields = ['image', 'caption', 'tags']
        widgets = {
            'tags': TagWidget(attrs={'placeholder': 'Ajouter des tags séparés par des virgules'})
        }


class BlogForm(forms.ModelForm):
    class Meta:
        model = models.Blog
        fields = ['title', 'content', 'tags']
        widgets = {
            'tags': TagWidget(attrs={'placeholder': 'Ajouter des tags séparés par des virgules'}),
           
        }


class DeleteBlogForm(forms.Form):
    delete_blog = forms.BooleanField(
        widget=forms.HiddenInput,
        initial=True,
        required=False,
    )


from django.contrib.auth import get_user_model
User = get_user_model()

class FollowUsersForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['follows']
        widgets = {
            'follows': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # filtrer uniquement les créateurs
        self.fields['follows'].queryset = User.objects.filter(role=User.CREATOR)