from django import forms
from .models import Household, Transaction, Category, Store, FamilyMember
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

def bootstrapify(form):
    for field in form.fields.values():
        widget = field.widget

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs['class'] = 'form-check-input'
        elif isinstance(widget, forms.RadioSelect):
            widget.attrs['class'] = 'form-check-input'
        elif isinstance(widget, forms.Select):
            widget.attrs['class'] = 'form-select'
        else:
            widget.attrs['class'] = 'form-control'


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bootstrapify(self)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bootstrapify(self)


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'store', 'category', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        household = kwargs.pop('household', None)
        super().__init__(*args, **kwargs)

        if household:
            self.fields['category'].queryset = Category.objects.filter(
                household=household, deleted_at__isnull=True
            ).order_by('name')
            self.fields['store'].queryset = Store.objects.filter(
                household=household, deleted_at__isnull=True
            ).order_by('name')

        # Set default date to today if not already set
        if not self.initial.get('date'):
            self.initial['date'] = timezone.now().date()

        self.fields['store'].widget.attrs['data-has-defaults'] = 'true'

        bootstrapify(self)


class TransactionFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    category = forms.ModelChoiceField(
        queryset=Category.objects.none().order_by('name'),
        required=False
    )
    store = forms.ModelChoiceField(
        queryset=Store.objects.none().order_by('name'),
        required=False
    )

    member = forms.ModelChoiceField(
        queryset=FamilyMember.objects.none(),
        required=False,
        label="User"
    )

    min_amount = forms.DecimalField(required=False, decimal_places=2)
    max_amount = forms.DecimalField(required=False, decimal_places=2)

    description = forms.CharField(required=False, label="Description contains")

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)

        if household:
            self.fields['category'].queryset = Category.objects.filter(
                household=household,
                deleted_at__isnull=True
            )
            self.fields['store'].queryset = Store.objects.filter(
                household=household,
                deleted_at__isnull=True
            )
            self.fields['member'].queryset = household.members.all()
        self.fields['member'].label_from_instance = lambda obj: obj.user.first_name

        bootstrapify(self)

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'default_category']

    def __init__(self, *args, **kwargs):
        household = kwargs.pop('household', None)
        super().__init__(*args, **kwargs)

        if household:
            self.fields['default_category'].queryset = Category.objects.filter(
                household=household,
                income_expense='EX',
                deleted_at__isnull=True
            )

        bootstrapify(self)

class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )
