# blog/forms.py
from django import forms
from . import models

class PhotoForm(forms.ModelForm):
    class Meta:
        model = models.Photo
        fields = ['image', 'caption']


class BlogForm(forms.ModelForm):
    class Meta:
        model = models.Blog
        fields = ['title', 'content']


# blog/forms.py
class DeleteBlogForm(forms.Form):
    delete_blog = forms.BooleanField(
        widget=forms.HiddenInput,
        initial=True,
        required=False,   # <- rendu non obligatoire
    )