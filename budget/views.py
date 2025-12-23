from calendar import monthrange
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm, CategoriesForm, TransactionForm, TransactionFilterForm, StoreForm
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


class DashboardFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    

@login_required
def dashboard(request):
    member = request.user.familymember
    household = member.household
    today = timezone.now().date()
    
    # Default date range: current month
    start_date = request.GET.get('start_date', today.replace(day=1))
    end_date = request.GET.get('end_date', today)

    # Recent transactions
    recent_transactions = Transaction.objects.filter(
        member__household=household
    ).order_by('-date')[:10]

    # Categories and budgets
    categories = Category.objects.filter(household=household, deleted_at__isnull=True)
    summary = []
    for category in categories:
        # Budget for this month (or start_date month)
        budget = Budget.get_budget_for_range(household, category, start_date, end_date)
        spent = Transaction.objects.filter(
            category=category,
            date__range=(start_date, end_date)
        ).aggregate(total=Sum('amount'))['total'] or 0
        summary.append({
            'category': category.name,
            'budget': budget if budget else 0,
            'spent': spent,
            'income_expense': category.income_expense
        })

    filter_form = DashboardFilterForm(initial={
        'start_date': start_date,
        'end_date': end_date
    })

    return render(request, 'budget/dashboard.html', {
        'recent_transactions': recent_transactions,
        'summary': summary,
        'month': f"{start_date.strftime('%B %Y')} - {end_date.strftime('%B %Y')}",
        'filter_form': filter_form
    })


@login_required
def category_list(request):
    household = request.user.familymember.household
    today = timezone.now().date()

    # All active categories
    categories = Category.objects.filter(household=household, deleted_at__isnull=True).order_by('-is_active', 'name')

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
            category = Category.objects.create(
                household=household,
                name=form.cleaned_data['name'],
                income_expense=form.cleaned_data['income_expense'],
                fixed=form.cleaned_data['fixed'],
                necessity=form.cleaned_data['necessity'],
                is_active=form.cleaned_data['is_active']
            )
            monthly_amount = form.cleaned_data.get('monthly_amount')
            if monthly_amount:
                Budget.objects.create(
                    household=household,
                    category=category,
                    monthly_amount=monthly_amount,
                    start_date=timezone.now().date()
                )
            return redirect('category_list')
    else:
        form = CategoriesForm(initial={'is_active': True})

    return render(request, 'budget/category_form.html', {'form': form, 'action': 'Create'})


@login_required
def category_update(request, pk):
    household = request.user.familymember.household
    category = get_object_or_404(Category, pk=pk, household=household)

    today = timezone.now().date()
    budget = Budget.get_budget_for_month(household, category, today.year, today.month)

    if request.method == "POST":
        form = CategoriesForm(request.POST)
        if form.is_valid():
            category.name = form.cleaned_data['name']
            category.income_expense = form.cleaned_data['income_expense']
            category.fixed = form.cleaned_data['fixed']
            category.necessity = form.cleaned_data['necessity']
            category.is_active = form.cleaned_data['is_active']
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
        form = CategoriesForm(initial={
            'name': category.name,
            'income_expense': category.income_expense,
            'fixed': category.fixed,
            'necessity': category.necessity,
            'monthly_amount': budget.monthly_amount if budget else None,
            'is_active': category.is_active
        })

    return render(request, 'budget/category_form.html', {'form': form, 'action': 'Edit'})


@login_required
def transaction_create(request):
    household = request.user.familymember.household

    if request.method == 'POST':
        form = TransactionForm(request.POST, household=household)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.member = request.user.familymember
            transaction.save()
            messages.success(request, "Transaction created successfully!")
            return redirect('transaction_list')  # or wherever you want to go
    else:
        form = TransactionForm(household=household)  # pass household to limit choices

    return render(request, 'budget/transaction_form.html', {'form': form, 'action': 'Create'})


@login_required
def store_list(request):
    household = request.user.familymember.household
    stores = Store.objects.filter(
        household=household,
        deleted_at__isnull=True
    ).order_by('name')

    return render(request, 'budget/store_list.html', {
        'stores': stores
    })


@login_required
def store_create(request):
    household = request.user.familymember.household

    if request.method == "POST":
        form = StoreForm(request.POST, household=household)
        if form.is_valid():
            store = form.save(commit=False)
            store.household = household
            store.save()
            return redirect('store_list')
    else:
        form = StoreForm(household=household)

    return render(request, 'budget/store_form.html', {
        'form': form,
        'action': 'Create'
    })


@login_required
def transaction_list(request):
    household = request.user.familymember.household

    transactions = Transaction.objects.filter(
        member__household=household,
        deleted_at__isnull=True
    ).select_related(
        'category', 'store', 'member__user'
    ).order_by('-date')

    filter_form = TransactionFilterForm(
        request.GET or None,
        household=household
    )

    if filter_form.is_valid():
        data = filter_form.cleaned_data

        if data['start_date']:
            transactions = transactions.filter(date__date__gte=data['start_date'])

        if data['end_date']:
            transactions = transactions.filter(date__date__lte=data['end_date'])

        if data['category']:
            transactions = transactions.filter(category=data['category'])

        if data['store']:
            transactions = transactions.filter(store=data['store'])

        if data['member']:
            transactions = transactions.filter(member=data['member'])

        if data['min_amount'] is not None:
            transactions = transactions.filter(amount__gte=data['min_amount'])

        if data['max_amount'] is not None:
            transactions = transactions.filter(amount__lte=data['max_amount'])

        if data['description']:
            transactions = transactions.filter(
                description__icontains=data['description']
            )

    return render(request, 'budget/transaction_list.html', {
        'transactions': transactions,
        'filter_form': filter_form,
    })


@login_required
def transaction_update(request, pk):
    household = request.user.familymember.household
    transaction = get_object_or_404(Transaction, pk=pk, member__household=household)

    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, household=household)
        if form.is_valid():
            updated_transaction = form.save(commit=False)
            updated_transaction.member = request.user.familymember 
            updated_transaction.save()
            return redirect('transaction_list') 
    else:
        form = TransactionForm(instance=transaction, household=household)

    return render(request, 'budget/transaction_form.html', {
        'form': form,
        'action': 'Edit'
    })