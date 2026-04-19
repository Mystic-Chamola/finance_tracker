from django.contrib import admin
from .models import (
    Expense, Budget, CategoryBudget, RecurringExpense, SavingsGoal,
    SavingsContribution, Income, Bill, Notification, UserProfile,
    Currency, DailyAnalytics
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_currency')
    search_fields = ('user__username', 'user__email')


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'rate_to_usd', 'updated_at')
    search_fields = ('code', 'name')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'monthly_limit')


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'monthly_limit')
    list_filter = ('category',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'category', 'date')
    list_filter = ('category', 'date')
    search_fields = ('title', 'user__username')


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'category', 'interval', 'next_due', 'is_active')
    list_filter = ('interval', 'is_active', 'category')


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'target_amount', 'current_amount', 'deadline', 'is_completed')
    list_filter = ('is_completed',)


@admin.register(SavingsContribution)
class SavingsContributionAdmin(admin.ModelAdmin):
    list_display = ('goal', 'amount', 'date')
    list_filter = ('date',)


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'category', 'date')
    list_filter = ('category', 'date')


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'due_date', 'is_paid', 'is_recurring')
    list_filter = ('is_paid', 'is_recurring', 'due_date')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')


@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'active_users', 'total_requests', 'expenses_created',
        'income_created', 'bills_created', 'goals_created', 'reports_generated'
    )
    list_filter = ('date',)
    date_hierarchy = 'date'