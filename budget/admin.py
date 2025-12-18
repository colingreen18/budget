from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import FamilyMember, Household, Category, Store, Transaction, RecurringTransaction, Budget

# -------------------------
# Household
# -------------------------
@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at', 'deleted_at')
    search_fields = ('name',)


class FamilyMemberInline(admin.StackedInline):
    model = FamilyMember
    can_delete = False
    verbose_name_plural = 'Family Member Info'
    fk_name = 'user'
    readonly_fields = ('household', 'role', 'joined_at')


class UserAdmin(BaseUserAdmin):
    inlines = (FamilyMemberInline,)

    # optionally display email and full name in list view
    list_display = ('username', 'email', 'first_name', 'last_name')

# -------------------------
# FamilyMember
# -------------------------
@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'household', 'role', 'joined_at')
    list_filter = ('household', 'role')
    search_fields = ('user__username',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(household=request.user.familymember.household)
        return qs


# -------------------------
# Category
# -------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'household', 'income_expense', 'fixed', 'necessity', 'created_at')
    list_filter = ('household', 'income_expense', 'fixed', 'necessity')
    search_fields = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(household=request.user.familymember.household)
        return qs


# -------------------------
# Store
# -------------------------
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'household', 'default_category', 'created_at')
    list_filter = ('household',)
    search_fields = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(household=request.user.familymember.household)
        return qs


# -------------------------
# Transaction
# -------------------------
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'member', 'amount', 'category', 'store')
    list_filter = ('category', 'store', 'member', 'date')
    search_fields = ('description', 'member__user__username', 'category__name', 'store__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(member__household=request.user.familymember.household)
        return qs


# -------------------------
# RecurringTransaction
# -------------------------
@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('member', 'amount', 'category', 'store', 'interval_count', 'interval_unit', 'start_date', 'end_date')
    list_filter = ('interval_unit', 'member', 'category', 'store')
    search_fields = ('description', 'member__user__username', 'category__name', 'store__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(member__household=request.user.familymember.household)
        return qs


# -------------------------
# Budget
# -------------------------
@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('household', 'category', 'monthly_amount', 'start_date', 'end_date')
    list_filter = ('household', 'category')
    search_fields = ('category__name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'familymember'):
            return qs.filter(household=request.user.familymember.household)
        return qs


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
