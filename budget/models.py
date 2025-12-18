from calendar import monthrange
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Household(models.Model):
    name = models.CharField(max_length=200)
    invite_code = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return self.name


class FamilyMember(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True)
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members",
    )
    role = models.CharField(max_length=50)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.household.name})"


class Category(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    fixed = models.BooleanField(default=False)
    necessity = models.BooleanField(default=False)
    income_expense = models.CharField(
        max_length=2,
        choices=[('IN', 'Income'),('EX', 'Expense')],
        default='EX'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="stores",
    )
    name = models.CharField(max_length=100)
    default_category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_stores"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name


class Transaction(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateTimeField(default=timezone.now)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    member = models.ForeignKey(FamilyMember, on_delete=models.PROTECT, related_name="transactions")
    description = models.CharField(max_length=500, null=True, blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category', 'date']),  # useful for category/month queries
            models.Index(fields=['member', 'date']),    # useful for member/month queries
        ]

    def __str__(self):
        return f"{self.date.date()} - {self.member.user.username} - {self.amount} {self.category.name}"


class RecurringTransaction(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="recurring_transactions")
    store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.SET_NULL, related_name="recurring_transactions")
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, related_name="recurring_transactions")
    description = models.CharField(max_length=500, null=True, blank=True,)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    last_generated = models.DateField(null=True, blank=True)
    interval_count = models.PositiveIntegerField(default=1)
    interval_unit = models.CharField(choices=[('DAYS','Days'),('WEEKS','Weeks'),('MONTHS','Months'), ('YEARS','Years')], max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)


    @property
    def next_date(self):
        if not self.last_generated:
            return self.start_date
        if self.interval_unit == 'DAYS':
            return self.last_generated + timedelta(days=self.interval_count)
        elif self.interval_unit == 'WEEKS':
            return self.last_generated + timedelta(weeks=self.interval_count)
        elif self.interval_unit == 'MONTHS':
            return self.last_generated + relativedelta(months=self.interval_count)
        elif self.interval_unit == 'YEARS':
            return self.last_generated + relativedelta(years=self.interval_count)

    def __str__(self):
        return f"{self.member.user.username} - {self.amount} - {self.category.name} (Every {self.interval_count} {self.interval_unit.lower()})"


class Budget(models.Model):
    household = models.ForeignKey('Household', on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name="budgets")
    monthly_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('household', 'category', 'start_date')
        indexes = [
            models.Index(fields=['household', 'category', 'start_date']),
            models.Index(fields=['household', 'category', 'end_date']),
        ]

    def __str__(self):
        return f"{self.household.name} - {self.category.name} - {self.monthly_amount} from {self.start_date}"

    def update_amount(self, new_amount, start_date=None):
        """
        Update the budget amount in a time-versioned way:
        - End the current row
        - Create a new row with the new amount
        """
        start_date = start_date or timezone.now().date()

        if start_date < self.start_date:
            raise ValueError("New start_date cannot be before the current budget's start_date.")

        # End current budget row if ongoing
        if self.end_date is None:
            self.end_date = start_date - timedelta(days=1)
            self.save()

        # Create new Budget row
        return Budget.objects.create(
            household=self.household,
            category=self.category,
            monthly_amount=new_amount,
            start_date=start_date
        )


    @staticmethod
    def get_budget_for_month(household, category, year, month):
        """
        Returns the Budget row for the given household, category, and month.
        """
        # Calculate first and last day of the month
        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])

        budget = Budget.objects.filter(
            household=household,
            category=category,
            start_date__lte=month_end
        ).filter(
            Q(end_date__gte=month_start) | Q(end_date__isnull=True)
        ).first()

        return budget

