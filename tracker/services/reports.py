import csv
import logging
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from ..models import Expense, Income, CategoryBudget
from ..audit import log_audit

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, user):
        self.user = user
        self.now = timezone.now()

    def generate_csv(self, year, month, category_filter=None):
        try:
            if year and month:
                try:
                    year, month = int(year), int(month)
                    selected_date = datetime(year, month, 1).date()
                except (ValueError, TypeError):
                    selected_date = self.now.date().replace(day=1)
            else:
                selected_date = self.now.date().replace(day=1)

            expenses = Expense.objects.filter(
                user=self.user, date__year=selected_date.year, date__month=selected_date.month
            ).order_by('-date')
            if category_filter:
                expenses = expenses.filter(category__iexact=category_filter)

            response = HttpResponse(content_type='text/csv')
            filename = f"expenses_{selected_date.strftime('%Y_%m')}"
            if category_filter:
                filename += f"_{category_filter.lower()}"
            filename += ".csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            writer.writerow(['Title', 'Amount', 'Category', 'Date'])
            for expense in expenses:
                writer.writerow([expense.title, str(expense.amount), expense.category, expense.date.strftime('%Y-%m-%d')])
            log_audit(self.user, 'EXPORT_CSV', f'Period: {selected_date.strftime("%Y-%m")}')
            return response, None
        except Exception as e:
            logger.exception("Error generating CSV export")
            return None, 'An error occurred while generating the export.'

    def get_report_context(self, year, month, report_type='monthly'):
        if report_type == 'yearly':
            if year:
                try:
                    year = int(year)
                    selected_date = datetime(year, 1, 1).date()
                except (ValueError, TypeError):
                    selected_date = self.now.date().replace(month=1, day=1)
            else:
                selected_date = self.now.date().replace(month=1, day=1)
            period_label = f"Year {selected_date.year}"
            income_qs = Income.objects.filter(user=self.user, date__year=selected_date.year)
            expenses_qs = Expense.objects.filter(user=self.user, date__year=selected_date.year)
        else:
            if year and month:
                try:
                    year, month = int(year), int(month)
                    selected_date = datetime(year, month, 1).date()
                except (ValueError, TypeError):
                    selected_date = self.now.date().replace(day=1)
            else:
                selected_date = self.now.date().replace(day=1)
            period_label = selected_date.strftime("%B %Y")
            income_qs = Income.objects.filter(user=self.user, date__year=selected_date.year, date__month=selected_date.month)
            expenses_qs = Expense.objects.filter(user=self.user, date__year=selected_date.year, date__month=selected_date.month)

        total_income = income_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
        net_savings = total_income - total_expenses

        category_data = expenses_qs.values('category').annotate(total=Sum('amount')).order_by('-total')
        categories = [item['category'] for item in category_data]
        amounts = [float(item['total']) for item in category_data]

        category_budget_status = []
        if report_type == 'monthly':
            category_budgets = {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=self.user)}
            for cat_code, cat_name in Expense.CATEGORY_CHOICES:
                spent = float(sum(item['total'] for item in category_data if item['category'] == cat_code))
                limit = float(category_budgets.get(cat_code, 0))
                if limit > 0:
                    percentage = min(100, (spent / limit) * 100)
                    remaining = limit - spent
                    over = spent > limit
                else:
                    percentage = remaining = 0
                    over = False
                category_budget_status.append({
                    'category': cat_code, 'display': cat_name, 'spent': spent,
                    'limit': limit, 'percentage': percentage, 'remaining': remaining, 'over': over,
                })

        top_expenses = expenses_qs.order_by('-amount')[:10]
        current_year = self.now.year
        years_range = range(current_year - 5, current_year + 1)
        months = [{'value': i, 'name': datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]

        return {
            'report_type': report_type,
            'period_label': period_label,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_savings': net_savings,
            'categories': categories,
            'amounts': amounts,
            'category_budget_status': category_budget_status,
            'top_expenses': top_expenses,
            'selected_year': selected_date.year,
            'selected_month': selected_date.month if report_type == 'monthly' else None,
            'years_range': years_range,
            'months': months,
        }