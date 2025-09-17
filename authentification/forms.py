from django import forms

class LoginForm(forms.Form):
    username = forms.CharField(
        label="",
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': ''})
    )
    password = forms.CharField(
        label="",
        widget=forms.PasswordInput(attrs={'placeholder': ''})
    )