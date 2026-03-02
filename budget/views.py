from calendar import monthrange
from datetime import datetime, date, timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm, CategoriesForm, TransactionForm, TransactionFilterForm, StoreForm, DateRangeForm
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
    household = request.user.familymember.household
    today = timezone.now().date()

    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    income_expense_filter = request.GET.get('income_expense', '')
    fixed_filter = request.GET.get('fixed', '')
    necessity_filter = request.GET.get('necessity', '')

    # Default to current month if no dates provided
    if not start_date or not end_date:
        start_date = today.replace(day=1)
        end_date = date(today.year, today.month, monthrange(today.year, today.month)[1])
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Initialize filter form
    filter_form = DateRangeForm(initial={
        'start_date': start_date,
        'end_date': end_date
    })

    # Get recent transactions - filter by member's household
    recent_transactions = Transaction.objects.filter(
        member__household=household,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('category').order_by('-date')[:10]

    # Calculate actual income and expenses
    actual_income = 0
    actual_necessary_expenses = 0
    actual_unnecessary_expenses = 0

    all_transactions = Transaction.objects.filter(
        member__household=household,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('category')

    for trans in all_transactions:
        if trans.category.income_expense == 'IN':
            actual_income += trans.amount
        else:
            if trans.category.necessity:
                actual_necessary_expenses += trans.amount
            else:
                actual_unnecessary_expenses += trans.amount

    actual_total_expenses = actual_necessary_expenses + actual_unnecessary_expenses
    actual_net = actual_income - actual_total_expenses

    # Get all categories for the household
    categories = Category.objects.filter(
        household=household,
        is_active=True,
        deleted_at__isnull=True
    ).order_by('name')

    # Apply filters
    if income_expense_filter:
        categories = categories.filter(income_expense=income_expense_filter)
    if fixed_filter:
        categories = categories.filter(fixed=(fixed_filter == 'true'))
    if necessity_filter:
        categories = categories.filter(necessity=(necessity_filter == 'true'))

    summary = []
    for cat in categories:
        # Get budget for the date range
        budget_amount = Budget.get_budget_for_range(household, cat, start_date, end_date)

        # Get actual spending/income for this category
        spent = Transaction.objects.filter(
            member__household=household,
            category=cat,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or 0

        summary.append({
            'category': cat.name,
            'budget': float(budget_amount),
            'spent': float(spent)
        })

    return render(request, 'budget/dashboard.html', {
        'recent_transactions': recent_transactions,
        'summary': summary,
        'filter_form': filter_form,
        'start_date': start_date,
        'end_date': end_date,
        'actual_income': actual_income,
        'actual_necessary_expenses': actual_necessary_expenses,
        'actual_unnecessary_expenses': actual_unnecessary_expenses,
        'actual_total_expenses': actual_total_expenses,
        'actual_net': actual_net,
        'income_expense_filter': income_expense_filter,
        'fixed_filter': fixed_filter,
        'necessity_filter': necessity_filter,
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

    total_income = 0
    total_necessary_expenses = 0
    total_unnecessary_expenses = 0

    for cat in categories:
        budget = Budget.get_budget_for_month(household, cat, today.year, today.month)
        budget_amount = budget.monthly_amount if budget else 0

        data = {
            'category': cat,
            'budget': budget.monthly_amount if budget else None
        }

        if cat.income_expense == 'IN':
            income_categories.append(data)
            if budget_amount:
                total_income += budget_amount
        else:
            expense_categories.append(data)
            if budget_amount:
                if cat.necessity:
                    total_necessary_expenses += budget_amount
                else:
                    total_unnecessary_expenses += budget_amount

    total_expenses = total_necessary_expenses + total_unnecessary_expenses
    projected_savings = total_income - total_expenses

    return render(request, 'budget/category_list.html', {
        'income_categories': income_categories,
        'expense_categories': expense_categories,
        'total_income': total_income,
        'total_necessary_expenses': total_necessary_expenses,
        'total_unnecessary_expenses': total_unnecessary_expenses,
        'total_expenses': total_expenses,
        'projected_savings': projected_savings,
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
def category_delete(request, pk):
    household = request.user.familymember.household
    category = get_object_or_404(Category, pk=pk, household=household)

    # Soft delete
    category.deleted_at = timezone.now()
    category.is_active = False  # optional: hide in dropdowns/forms
    category.save()

    return redirect('category_list')


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
        deleted_at__isnull=True,
        is_active=True
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
def store_update(request, pk):
    household = request.user.familymember.household
    store = get_object_or_404(Store, pk=pk, household=household)  # ensure user only edits their own stores

    if request.method == "POST":
        form = StoreForm(request.POST, instance=store, household=household)
        if form.is_valid():
            form.save()
            return redirect('store_list')
    else:
        form = StoreForm(instance=store, household=household)

    return render(request, 'budget/store_form.html', {
        'form': form,
        'action': 'Update'
    })


@login_required
def store_delete(request, pk):
    household = request.user.familymember.household
    store = get_object_or_404(Store, pk=pk, household=household)

    # Soft delete
    store.deleted_at = timezone.now()
    store.is_active = False  # optional: mark inactive
    store.save()

    return redirect('store_list')


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


@login_required
def transaction_delete(request, pk):
    # Only allow deleting transactions in the current user's household
    household = request.user.familymember.household
    transaction = get_object_or_404(Transaction, pk=pk, category__household=household)

    if request.method == "POST":
        transaction.delete()
        return redirect('transaction_list')

    # Optional: show a confirmation page before deletion
    return render(request, 'budget/transaction_confirm_delete.html', {
        'transaction': transaction
    })


@login_required
def profile(request):
    if request.method == 'POST':
        user = request.user
        first = request.POST.get('first_name')
        last = request.POST.get('last_name')
        email = request.POST.get('email')
        pw1 = request.POST.get('password1')
        pw2 = request.POST.get('password2')

        user.first_name = first
        user.last_name = last
        user.email = email

        # Update password if provided
        if pw1 or pw2:
            if pw1 == pw2:
                user.set_password(pw1)
                update_session_auth_hash(request, user)  # keep user logged in
            else:
                messages.error(request, "Passwords do not match.")
                return redirect('profile')

        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')

    return render(request, 'budget/profile.html')


@login_required
def insights(request):
    household = request.user.familymember.household
    today = timezone.now().date()

    # Get the last 12 months of data
    twelve_months_ago = today - timedelta(days=365)

    # Monthly spending trend (last 12 months)
    monthly_spending = []
    monthly_income = []
    monthly_labels = []
    savings_rate = []

    for i in range(12):
        # Calculate month
        month_date = today - timedelta(days=30 * i)
        month_start = date(month_date.year, month_date.month, 1)
        month_end = date(month_date.year, month_date.month, monthrange(month_date.year, month_date.month)[1])

        # Get transactions for this month
        month_transactions = Transaction.objects.filter(
            member__household=household,
            date__gte=month_start,
            date__lte=month_end
        ).select_related('category')

        # Calculate income and expenses
        income = 0
        expenses = 0
        for trans in month_transactions:
            if trans.category.income_expense == 'IN':
                income += trans.amount
            else:
                expenses += trans.amount

        # Calculate savings rate
        if income > 0:
            rate = ((income - expenses) / income) * 100
        else:
            rate = 0

        monthly_spending.insert(0, float(expenses))
        monthly_income.insert(0, float(income))
        monthly_labels.insert(0, month_start.strftime('%b %Y'))
        savings_rate.insert(0, float(rate))

    # Category breakdown (current month)
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    category_breakdown = {}
    category_transactions = Transaction.objects.filter(
        member__household=household,
        date__gte=month_start,
        date__lte=month_end,
        category__income_expense='EX'  # Only expenses for pie chart
    ).select_related('category')

    for trans in category_transactions:
        if trans.category.name not in category_breakdown:
            category_breakdown[trans.category.name] = 0
        category_breakdown[trans.category.name] += float(trans.amount)

    # Budget adherence score (current month)
    categories = Category.objects.filter(
        household=household,
        is_active=True,
        deleted_at__isnull=True
    )

    total_categories = 0
    categories_on_budget = 0
    category_adherence = []

    for cat in categories:
        budget = Budget.get_budget_for_month(household, cat, today.year, today.month)
        if budget and budget.monthly_amount > 0:
            spent = Transaction.objects.filter(
                member__household=household,
                category=cat,
                date__gte=month_start,
                date__lte=month_end
            ).aggregate(total=Sum('amount'))['total'] or 0

            adherence_pct = (spent / budget.monthly_amount) * 100
            category_adherence.append({
                'category': cat.name,
                'adherence': float(adherence_pct),
                'budget': float(budget.monthly_amount),
                'spent': float(spent),
                'on_budget': spent <= budget.monthly_amount
            })

            total_categories += 1
            if spent <= budget.monthly_amount:
                categories_on_budget += 1

    # Calculate overall adherence score
    if total_categories > 0:
        budget_adherence_score = (categories_on_budget / total_categories) * 100
    else:
        budget_adherence_score = 0

    return render(request, 'budget/insights.html', {
        'monthly_labels': monthly_labels,
        'monthly_spending': monthly_spending,
        'monthly_income': monthly_income,
        'savings_rate': savings_rate,
        'category_breakdown_labels': list(category_breakdown.keys()),
        'category_breakdown_values': list(category_breakdown.values()),
        'budget_adherence_score': budget_adherence_score,
        'category_adherence': category_adherence,
    })


def logout_view(request):
    logout(request)
    return redirect('login')