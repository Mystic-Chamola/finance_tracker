from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ..models import Expense, Income, Budget, CategoryBudget, SavingsGoal, Bill


class DashboardService:
    """Encapsulates all data aggregation for the dashboard."""

    def __init__(self, user):
        self.user = user
        self.now = timezone.now()

    def get_selected_date(self, year, month):
        """Parse year/month from request or default to current month."""
        if year and month:
            try:
                return datetime(int(year), int(month), 1).date()
            except (ValueError, TypeError):
                pass
        return self.now.date().replace(day=1)

    def get_budget(self):
        """Return the user's global monthly budget."""
        obj, _ = Budget.objects.get_or_create(user=self.user, defaults={'monthly_limit': 0})
        return obj.monthly_limit

    def get_category_budgets(self):
        """Return a dict of category -> monthly_limit."""
        return {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=self.user)}

    def get_monthly_totals(self, year, month):
        """Return (total_spent, total_income) for a given month."""
        spent = Expense.objects.filter(
            user=self.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        income = Income.objects.filter(
            user=self.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        return spent, income

    def get_category_breakdown(self, year, month, category_filter=None):
        """Return categories, amounts, and spending dict for pie chart."""
        qs = Expense.objects.filter(user=self.user, date__year=year, date__month=month)
        if category_filter:
            qs = qs.filter(category__iexact=category_filter)
        data = qs.values('category').annotate(total=Sum('amount')).order_by('-total')
        categories = [item['category'] for item in data]
        amounts = [float(item['total']) for item in data]
        spending_dict = {item['category']: item['total'] for item in data}
        return categories, amounts, spending_dict

    def get_monthly_trends(self, base_date, months_back=5, category_filter=None):
        """Return month_labels, monthly_totals, monthly_income_totals for last N months."""
        start_date = base_date - relativedelta(months=months_back)
        expense_qs = Expense.objects.filter(user=self.user, date__gte=start_date)
        income_qs = Income.objects.filter(user=self.user, date__gte=start_date)
        if category_filter:
            expense_qs = expense_qs.filter(category__iexact=category_filter)

        expense_data = expense_qs.annotate(month=TruncMonth('date')).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        expense_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in expense_data}

        income_data = income_qs.annotate(month=TruncMonth('date')).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        income_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in income_data}

        month_labels = []
        monthly_totals = []
        monthly_income_totals = []
        for i in range(months_back, -1, -1):
            month_date = base_date - relativedelta(months=i)
            key = month_date.strftime('%Y-%m')
            month_labels.append(month_date.strftime('%b %Y'))
            monthly_totals.append(expense_dict.get(key, 0))
            monthly_income_totals.append(income_dict.get(key, 0))

        return month_labels, monthly_totals, monthly_income_totals

    def get_daily_spending(self, year, month, category_filter=None):
        """Return daily_labels and daily_totals for a month."""
        qs = Expense.objects.filter(user=self.user, date__year=year, date__month=month)
        if category_filter:
            qs = qs.filter(category__iexact=category_filter)
        daily_data = qs.annotate(day=TruncDay('date')).values('day').annotate(
            total=Sum('amount')
        ).order_by('day')
        daily_dict = {item['day'].day: float(item['total']) for item in daily_data}

        next_month = datetime(year, month, 1).date() + relativedelta(months=1)
        days_in_month = (next_month - timedelta(days=1)).day
        daily_labels = list(range(1, days_in_month + 1))
        daily_totals = [daily_dict.get(day, 0) for day in daily_labels]
        return daily_labels, daily_totals

    def get_year_over_year(self, base_date):
        """Return (last_year_spent, last_year_income, last_year_label)."""
        last_year = base_date - relativedelta(years=1)
        spent = Expense.objects.filter(
            user=self.user, date__year=last_year.year, date__month=last_year.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        income = Income.objects.filter(
            user=self.user, date__year=last_year.year, date__month=last_year.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        return float(spent), float(income), last_year.strftime('%B %Y')

    def get_forecast(self, base_date, months_back=3):
        """Return forecast_months, forecast_values, forecast_next."""
        past_months = [(base_date - relativedelta(months=i)) for i in range(1, months_back + 1)]
        forecast_months = []
        forecast_values = []
        for past_date in past_months:
            spent = Expense.objects.filter(
                user=self.user, date__year=past_date.year, date__month=past_date.month
            ).aggregate(total=Sum('amount'))['total'] or 0
            forecast_months.append(past_date.strftime('%b %Y'))
            forecast_values.append(float(spent))
        forecast_next = sum(forecast_values) / len(forecast_values) if forecast_values else 0
        return forecast_months, forecast_values, forecast_next

    def get_category_budget_status(self, year, month, category_spending, category_budgets):
        """Return list of dicts with budget vs actual for each category."""
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

    def get_active_goals(self, limit=3):
        return SavingsGoal.objects.filter(user=self.user, is_completed=False).order_by('-created_at')[:limit]

    def get_upcoming_bills(self, days=7):
        return Bill.objects.filter(
            user=self.user, is_paid=False,
            due_date__gte=self.now.date(),
            due_date__lte=self.now.date() + relativedelta(days=days)
        ).order_by('due_date')