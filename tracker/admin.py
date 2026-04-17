from django.contrib import admin
from .models import Expense, Budget

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title','user','amount','category','date')
    list_filter = ('category', 'date')
    search_fields = ('title',)

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user','monthly_limit')