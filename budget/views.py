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
    transaction = get_object_or_404(Transaction, pk=pk, member__household=household)

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
    from dateutil.relativedelta import relativedelta
    household = request.user.familymember.household
    today = timezone.now().date()

    # --- Monthly chart data (last 12 months) ---
    monthly_spending = []
    monthly_income = []
    monthly_labels = []
    savings_rate = []
    cumulative_savings = []
    cumulative = 0

    for i in range(11, -1, -1):  # oldest to newest
        month_date = today.replace(day=1) - relativedelta(months=i)
        month_start = date(month_date.year, month_date.month, 1)
        month_end = date(month_date.year, month_date.month, monthrange(month_date.year, month_date.month)[1])

        month_transactions = Transaction.objects.filter(
            member__household=household,
            date__gte=month_start,
            date__lte=month_end
        ).select_related('category')

        income = 0
        expenses = 0
        for trans in month_transactions:
            if trans.category.income_expense == 'IN':
                income += float(trans.amount)
            else:
                expenses += float(trans.amount)

        rate = ((income - expenses) / income * 100) if income > 0 else 0
        cumulative += income - expenses

        monthly_spending.append(round(expenses, 2))
        monthly_income.append(round(income, 2))
        monthly_labels.append(month_start.strftime('%b %Y'))
        savings_rate.append(round(rate, 2))
        cumulative_savings.append(round(cumulative, 2))

    # --- Category budget details ---
    detail_mode = request.GET.get('detail_mode', 'month')
    selected_month = request.GET.get('selected_month', today.strftime('%Y-%m'))

    try:
        selected_month_date = datetime.strptime(selected_month, '%Y-%m').date()
    except ValueError:
        selected_month_date = today.replace(day=1)

    sel_year = selected_month_date.year
    sel_month = selected_month_date.month
    sel_month_start = date(sel_year, sel_month, 1)
    sel_month_end = date(sel_year, sel_month, monthrange(sel_year, sel_month)[1])

    categories = Category.objects.filter(
        household=household,
        is_active=True,
        deleted_at__isnull=True
    ).order_by('name')

    def get_spending(cat, start, end):
        return float(Transaction.objects.filter(
            member__household=household,
            category=cat,
            date__gte=start,
            date__lte=end
        ).aggregate(total=Sum('amount'))['total'] or 0)

    # Build list of months with actual transaction data
    earliest_tx = Transaction.objects.filter(
        member__household=household
    ).order_by('date').first()

    all_months = []        # all months from first tx to today (for remaining)
    completed_months = []  # excludes current month (for average)

    if earliest_tx:
        cursor = earliest_tx.date.date().replace(day=1)
        current_month_start = today.replace(day=1)
        while cursor <= current_month_start:
            all_months.append(cursor)
            if cursor < current_month_start:
                completed_months.append(cursor)
            cursor += relativedelta(months=1)

    # Month options: only months that have at least one transaction, newest first
    months_with_data = Transaction.objects.filter(
        member__household=household
    ).dates('date', 'month', order='DESC')

    month_options = [
        {'value': m.strftime('%Y-%m'), 'label': m.strftime('%B %Y')}
        for m in months_with_data
    ]

    # Ensure selected_month is valid; fall back to most recent
    valid_values = [o['value'] for o in month_options]
    if selected_month not in valid_values and month_options:
        selected_month = month_options[0]['value']
        selected_month_date = datetime.strptime(selected_month, '%Y-%m').date()
        sel_year = selected_month_date.year
        sel_month = selected_month_date.month
        sel_month_start = date(sel_year, sel_month, 1)
        sel_month_end = date(sel_year, sel_month, monthrange(sel_year, sel_month)[1])

    income_categories = []
    necessary_categories = []
    discretionary_categories = []

    avg_monthly_savings = None

    if detail_mode == 'average' and completed_months:
        # Calculate average monthly savings across all completed months
        total_savings = 0
        for m in completed_months:
            m_end = date(m.year, m.month, monthrange(m.year, m.month)[1])
            m_txs = Transaction.objects.filter(
                member__household=household,
                date__gte=m,
                date__lte=m_end
            ).select_related('category')
            m_income = sum(float(t.amount) for t in m_txs if t.category.income_expense == 'IN')
            m_expenses = sum(float(t.amount) for t in m_txs if t.category.income_expense != 'IN')
            total_savings += m_income - m_expenses
        avg_monthly_savings = round(total_savings / len(completed_months), 2)

    for cat in categories:
        if detail_mode == 'month':
            budget = Budget.get_budget_for_month(household, cat, sel_year, sel_month)
            display_budget = float(budget.monthly_amount) if budget else 0
            display_spent = get_spending(cat, sel_month_start, sel_month_end)
            adherence = (display_spent / display_budget * 100) if display_budget > 0 else None
            remaining = None
            if display_budget == 0 and display_spent == 0:
                continue

        elif detail_mode == 'average':
            if not completed_months:
                continue
            total_budget = 0
            total_spent = 0
            for m in completed_months:
                b = Budget.get_budget_for_month(household, cat, m.year, m.month)
                total_budget += float(b.monthly_amount) if b else 0
                m_end = date(m.year, m.month, monthrange(m.year, m.month)[1])
                total_spent += get_spending(cat, m, m_end)
            month_count = len(completed_months)
            display_budget = round(total_budget / month_count, 2)
            display_spent = round(total_spent / month_count, 2)
            adherence = (display_spent / display_budget * 100) if display_budget > 0 else None
            remaining = None
            if display_budget == 0 and display_spent == 0:
                continue

        elif detail_mode == 'remaining':
            if not all_months:
                continue
            cumul = 0
            for m in all_months:
                b = Budget.get_budget_for_month(household, cat, m.year, m.month)
                b_amt = float(b.monthly_amount) if b else 0
                m_end = date(m.year, m.month, monthrange(m.year, m.month)[1])
                cumul += b_amt - get_spending(cat, m, m_end)
            display_budget = None
            display_spent = None
            adherence = None
            remaining = round(cumul, 2)
        else:
            continue

        entry = {
            'category': cat.name,
            'adherence': adherence,
            'display_budget': display_budget,
            'display_spent': display_spent,
            'remaining': remaining,
            'on_budget': (display_spent <= display_budget) if (display_budget and display_spent is not None) else None,
        }

        if cat.income_expense == 'IN':
            income_categories.append(entry)
        elif cat.necessity:
            necessary_categories.append(entry)
        else:
            discretionary_categories.append(entry)

    def sort_key(e):
        if detail_mode == 'remaining':
            return e['remaining'] if e['remaining'] is not None else 0
        return e['adherence'] if e['adherence'] is not None else 0

    income_categories.sort(key=sort_key, reverse=True)
    necessary_categories.sort(key=sort_key, reverse=True)
    discretionary_categories.sort(key=sort_key, reverse=True)

    return render(request, 'budget/insights.html', {
        'monthly_labels': monthly_labels,
        'monthly_spending': monthly_spending,
        'monthly_income': monthly_income,
        'savings_rate': savings_rate,
        'cumulative_savings': cumulative_savings,
        'income_categories': income_categories,
        'necessary_categories': necessary_categories,
        'discretionary_categories': discretionary_categories,
        'detail_mode': detail_mode,
        'selected_month': selected_month,
        'month_options': month_options,
        'avg_monthly_savings': avg_monthly_savings,
    })

def logout_view(request):
    logout(request)
    return redirect('login')