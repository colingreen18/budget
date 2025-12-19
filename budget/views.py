from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm, CategoriesForm
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


@login_required
def category_list(request):
    household = request.user.familymember.household
    today = timezone.now().date()

    # All active categories
    categories = Category.objects.filter(household=household, deleted_at__isnull=True)

    # Split into income and expense
    income_categories = []
    expense_categories = []

    for cat in categories:
        budget = Budget.get_budget_for_month(household, cat, today.year, today.month)
        data = {
            'category': cat,
            'budget': budget.monthly_amount if budget else None
        }
        if cat.income_expense == 'IN':
            income_categories.append(data)
        else:
            expense_categories.append(data)

    return render(request, 'budget/category_list.html', {
        'income_categories': income_categories,
        'expense_categories': expense_categories
    })


@login_required
def category_create(request):
    household = request.user.familymember.household

    if request.method == "POST":
        form = CategoriesForm(request.POST)
        if form.is_valid():
            Category.objects.create(
                household=household,
                name=form.cleaned_data['name'],
                income_expense=form.cleaned_data['income_expense'],
                fixed=form.cleaned_data['fixed'],
                necessity=form.cleaned_data['necessity']
            )
            monthly_amount = form.cleaned_data.get('monthly_amount')
            if monthly_amount:
                Budget.objects.create(
                household=household,
                category=category,
                monthly_amount=monthly_amount,
                start_date=timezone.now().date()
            )
            return redirect('category_list')  # your list view
    else:
        form = CategoriesForm()

    return render(request, 'budget/category_form.html', {'form': form, 'action': 'Create'})


@login_required
def category_update(request, pk):
    household = request.user.familymember.household
    category = get_object_or_404(Category, pk=pk, household=household, deleted_at__isnull=True)

    # Get current budget for this category (if any)
    today = timezone.now().date()
    budget = Budget.get_budget_for_month(household, category, today.year, today.month)

    if request.method == "POST":
        form = CategoriesForm(request.POST)
        if form.is_valid():
            category.name = form.cleaned_data['name']
            category.income_expense = form.cleaned_data['income_expense']
            category.fixed = form.cleaned_data['fixed']
            category.necessity = form.cleaned_data['necessity']
            category.save()

            monthly_amount = form.cleaned_data.get('monthly_amount')
            if monthly_amount is not None:
                if budget:
                    budget.update_amount(monthly_amount)
                else:
                    Budget.objects.create(
                        household=household,
                        category=category,
                        monthly_amount=monthly_amount,
                        start_date=today
                    )
            return redirect('category_list')
    else:
        # GET request
        form = CategoriesForm(initial={
            'name': category.name,
            'income_expense': category.income_expense,
            'fixed': category.fixed,
            'necessity': category.necessity,
            'monthly_amount': budget.monthly_amount if budget else None,
        })

    return render(request, 'budget/category_form.html', {'form': form, 'action': 'Edit'})
