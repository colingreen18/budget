from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm
from .models import FamilyMember, Household, Category, Store, Transaction, RecurringTransaction, Budget

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            password = form.cleaned_data['password1']

        

            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password
            )

            if form.cleaned_data['household_name']:
                household = Household.objects.create(name=form.cleaned_data['household_name'])
                role = 'Owner'
            else:
                invite_code = form.cleaned_data['invite_code']
                household = get_object_or_404(Household, invite_code=invite_code)
                role = 'Member'

            FamilyMember.objects.create(user=user, household=household, role=role)
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()

    return render(request, 'budget/signup.html', {'form': form})


@login_required
def dashboard(request):
    member = request.user.familymember
    household = member.household

    # Get current month
    today = timezone.now().date()
    budgets = Budget.objects.filter(
        household=household,
        start_date__lte=today
    ).filter(Q(end_date__gte=today) | Q(end_date__isnull=True))

    transactions = Transaction.objects.filter(member__household=household).order_by('-date')[:10]
    recurring = RecurringTransaction.objects.filter(member__household=household)

    context = {
        'household': household,
        'budgets': budgets,
        'transactions': transactions,
        'recurring': recurring,
    }
    return render(request, 'budget/dashboard.html', context)