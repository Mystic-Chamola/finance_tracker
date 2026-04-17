from django.db.models import Sum
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Expense, Income, CategoryBudget, Notification, Bill

class DashboardService:
    def __init__(self, user):
        self.user = user
        self.now = timezone.now()

    def get_monthly_totals(self, year, month):
        expenses = Expense.objects.filter(
            user=self.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        income = Income.objects.filter(
            user=self.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        return expenses, income

    def get_category_breakdown(self, year, month):
        return Expense.objects.filter(
            user=self.user, date__year=year, date__month=month
        ).values('category').annotate(total=Sum('amount')).order_by('-total')

    def get_category_budget_status(self, year, month):
        category_budgets = {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=self.user)}
        category_spending = {item['category']: item['total'] for item in self.get_category_breakdown(year, month)}
        status = []
        for cat_code, cat_name in Expense.CATEGORY_CHOICES:
            spent = float(category_spending.get(cat_code, 0))
            limit = float(category_budgets.get(cat_code, 0))
            if limit > 0:
                percentage = min(100, (spent / limit) * 100)
                remaining = limit - spent
                over = spent > limit
            else:
                percentage = remaining = 0
                over = False
            status.append({
                'category': cat_code, 'display': cat_name, 'spent': spent,
                'limit': limit, 'percentage': percentage, 'remaining': remaining, 'over': over,
            })
        return status

    def get_upcoming_bills(self, days=7):
        return Bill.objects.filter(
            user=self.user, is_paid=False,
            due_date__gte=self.now.date(),
            due_date__lte=self.now.date() + relativedelta(days=days)
        ).order_by('due_date')

    # ... additional reusable query methods