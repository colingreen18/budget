from django import forms
from .models import Household
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class SignUpForm(forms.Form):
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(max_length=30, label="First Name")
    last_name = forms.CharField(max_length=30, label="Last Name")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    household_name = forms.CharField(max_length=200, required=False, label="New Household Name")
    invite_code = forms.UUIDField(required=False, label="Invite Code")

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['password1'] != cleaned_data['password2']:
            raise forms.ValidationError("Passwords do not match.")
        if not cleaned_data.get('household_name') and not cleaned_data.get('invite_code'):
            raise forms.ValidationError("Provide either a new household name or a valid invite code.")
        return cleaned_data
