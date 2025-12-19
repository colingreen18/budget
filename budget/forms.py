from django import forms
from .models import Household, Transaction, Category, Store
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

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


class CategoriesForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    income_expense = forms.ChoiceField(
        choices=[('EX', 'Expense'), ('IN', 'Income')],
        widget=forms.RadioSelect,
        initial='EX',
        label=""
    )
    fixed = forms.BooleanField(required=False)
    necessity = forms.BooleanField(required=False)
    monthly_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label="Budgeted Amount")
    is_active = forms.BooleanField(
    required=False,
    initial=True,
    label="Active")


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'category', 'store', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        household = kwargs.pop('household', None)  # pass household from view
        super().__init__(*args, **kwargs)

        if household:
            self.fields['category'].queryset = Category.objects.filter(
                household=household, deleted_at__isnull=True
            )
            self.fields['store'].queryset = Store.objects.filter(
                household=household, deleted_at__isnull=True
            )

        # Set default date to today if not already set
        if not self.initial.get('date'):
            self.initial['date'] = timezone.now().date()