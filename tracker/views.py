import csv
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash, logout
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.core.paginator import Paginator
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django_ratelimit.decorators import ratelimit

from .models import (
    Expense, Budget, RecurringExpense, SavingsGoal, SavingsContribution,
    Income, CategoryBudget, Bill, Notification, UserProfile, Currency
)
from .forms import (
    RegisterForm, ExpenseForm, BudgetForm, RecurringExpenseForm,
    SavingsGoalForm, SavingsContributionForm, IncomeForm, CategoryBudgetForm,
    BillForm, UserProfileForm, UserUpdateForm, CustomPasswordChangeForm, DeleteAccountForm
)
from .utils import create_notification, check_budget_alerts, check_category_budget_alerts, check_bill_reminders
from .audit import log_audit

# Set up logging for audit trail
audit_logger = logging.getLogger('tracker.audit')


# ============================================================
# BASE CLASS FOR PAGINATED LIST VIEWS
# ============================================================

class PaginatedListView(LoginRequiredMixin, ListView):
    """Base list view with pagination (20 items per page) and user filtering."""
    paginate_by = 20
    context_object_name = 'page_obj'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


# ============================================================
# CLASS-BASED LIST VIEWS
# ============================================================

class IncomeListView(PaginatedListView):
    model = Income
    template_name = 'tracker/income_list.html'
    ordering = ['-date']


class BillListView(PaginatedListView):
    model = Bill
    template_name = 'tracker/bill_list.html'
    ordering = ['is_paid', 'due_date']


class RecurringListView(PaginatedListView):
    model = RecurringExpense
    template_name = 'tracker/recurring_list.html'
    ordering = ['-is_active', 'next_due']


class GoalListView(PaginatedListView):
    model = SavingsGoal
    template_name = 'tracker/goal_list.html'
    ordering = ['-is_completed', '-created_at']


class NotificationListView(PaginatedListView):
    model = Notification
    template_name = 'tracker/notification_list.html'
    ordering = ['-created_at']


# ============================================================
# AUTHENTICATION (with rate limiting)
# ============================================================

@ratelimit(key='ip', rate='5/m', block=True)
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Budget.objects.create(user=user, monthly_limit=0)
            UserProfile.objects.create(user=user, preferred_currency='USD')
            log_audit(user, 'USER_REGISTERED', f'Email: {user.email}')
            messages.success(request, 'Registration successful. You can now log in.')
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()

    year = request.GET.get('year')
    month = request.GET.get('month')
    category_filter = request.GET.get('category', '').strip()

    if year and month:
        try:
            year, month = int(year), int(month)
            selected_date = datetime(year, month, 1).date()
        except (ValueError, TypeError):
            selected_date = now.date().replace(day=1)
    else:
        selected_date = now.date().replace(day=1)

    current_month, current_year = selected_date.month, selected_date.year

    budget_obj, _ = Budget.objects.get_or_create(user=user, defaults={'monthly_limit': 0})
    category_budgets = {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=user)}

    expenses_qs = Expense.objects.filter(
        user=user, date__year=current_year, date__month=current_month
    ).select_related('recurring_source')
    if category_filter:
        expenses_qs = expenses_qs.filter(category__iexact=category_filter)

    total_spent = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
    total_income = Income.objects.filter(
        user=user, date__year=current_year, date__month=current_month
    ).aggregate(total=Sum('amount'))['total'] or 0

    net_savings = total_income - total_spent
    remaining_budget = budget_obj.monthly_limit - total_spent
    over_budget = remaining_budget < 0

    paginator = Paginator(expenses_qs.order_by('-date'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    category_data = expenses_qs.values('category').annotate(total=Sum('amount')).order_by('-total')
    categories = [item['category'] for item in category_data]
    amounts = [float(item['total']) for item in category_data]
    category_spending = {item['category']: item['total'] for item in category_data}

    start_date = selected_date - relativedelta(months=5)
    monthly_qs = Expense.objects.filter(user=user, date__gte=start_date)
    if category_filter:
        monthly_qs = monthly_qs.filter(category__iexact=category_filter)
    monthly_expenses = monthly_qs.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
    monthly_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in monthly_expenses}
    month_labels = []
    monthly_totals = []
    for i in range(5, -1, -1):
        month_date = selected_date - relativedelta(months=i)
        month_key = month_date.strftime('%Y-%m')
        month_labels.append(month_date.strftime('%b %Y'))
        monthly_totals.append(monthly_dict.get(month_key, 0))

    monthly_income_qs = Income.objects.filter(user=user, date__gte=start_date)
    monthly_income_data = monthly_income_qs.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
    income_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in monthly_income_data}
    monthly_income_totals = [income_dict.get((selected_date - relativedelta(months=i)).strftime('%Y-%m'), 0) for i in range(5, -1, -1)]

    daily_expenses = expenses_qs.annotate(day=TruncDay('date')).values('day').annotate(total=Sum('amount')).order_by('day')
    daily_dict = {item['day'].day: float(item['total']) for item in daily_expenses}
    days_in_month = (selected_date + relativedelta(day=31)).replace(day=1) - timedelta(days=1)
    daily_labels = list(range(1, days_in_month.day + 1))
    daily_totals = [daily_dict.get(day, 0) for day in daily_labels]

    last_year_date = selected_date - relativedelta(years=1)
    last_year_spent = Expense.objects.filter(user=user, date__year=last_year_date.year, date__month=last_year_date.month).aggregate(total=Sum('amount'))['total'] or 0
    last_year_income = Income.objects.filter(user=user, date__year=last_year_date.year, date__month=last_year_date.month).aggregate(total=Sum('amount'))['total'] or 0

    past_months = [(selected_date - relativedelta(months=i)) for i in range(1, 4)]
    forecast_values = []
    forecast_months = []
    for past_date in past_months:
        spent = Expense.objects.filter(user=user, date__year=past_date.year, date__month=past_date.month).aggregate(total=Sum('amount'))['total'] or 0
        forecast_months.append(past_date.strftime('%b %Y'))
        forecast_values.append(float(spent))
    forecast_next = sum(forecast_values) / len(forecast_values) if forecast_values else 0

    category_budget_status = []
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
        category_budget_status.append({
            'category': cat_code, 'display': cat_name, 'spent': spent,
            'limit': limit, 'percentage': percentage, 'remaining': remaining, 'over': over,
        })

    active_goals = SavingsGoal.objects.filter(user=user, is_completed=False).order_by('-created_at')[:3]
    upcoming_bills = Bill.objects.filter(
        user=user, is_paid=False, due_date__gte=now.date(),
        due_date__lte=now.date() + relativedelta(days=7)
    ).order_by('due_date')

    check_budget_alerts(user, total_spent, budget_obj.monthly_limit)
    check_category_budget_alerts(user, category_spending, category_budgets)
    check_bill_reminders(user)

    context = {
        'page_obj': page_obj, 'total_spent': total_spent, 'total_income': total_income,
        'net_savings': net_savings, 'budget_limit': budget_obj.monthly_limit, 'remaining': remaining_budget,
        'over_budget': over_budget, 'categories': categories, 'amounts': amounts,
        'month_labels': month_labels, 'monthly_totals': monthly_totals, 'monthly_income_totals': monthly_income_totals,
        'current_month': selected_date, 'prev_month': selected_date - relativedelta(months=1),
        'next_month': selected_date + relativedelta(months=1), 'category_filter': category_filter,
        'active_goals': active_goals, 'category_budget_status': category_budget_status,
        'upcoming_bills': upcoming_bills, 'daily_labels': daily_labels, 'daily_totals': daily_totals,
        'last_year_spent': float(last_year_spent), 'last_year_income': float(last_year_income),
        'last_year_month': last_year_date.strftime('%B %Y'), 'forecast_months': forecast_months,
        'forecast_values': forecast_values, 'forecast_next': forecast_next,
    }
    return render(request, 'tracker/dashboard.html', context)


# ============================================================
# EXPENSES
# ============================================================

@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            log_audit(request.user, 'EXPENSE_ADDED', f'Title: {expense.title}, Amount: {expense.amount}')
            messages.success(request, 'Expense added successfully.')
            return redirect('dashboard')
    else:
        form = ExpenseForm()
    return render(request, 'tracker/add_expense.html', {'form': form})


@login_required
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'EXPENSE_UPDATED', f'ID: {pk}')
            messages.success(request, 'Expense updated successfully.')
            return redirect('dashboard')
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'tracker/edit_expense.html', {'form': form})


@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        log_audit(request.user, 'EXPENSE_DELETED', f'ID: {pk}')
        expense.delete()
        messages.success(request, 'Expense deleted.')
        return redirect('dashboard')
    return render(request, 'tracker/delete_expense.html', {'expense': expense})


# ============================================================
# BUDGETS
# ============================================================

@login_required
def set_budget(request):
    budget_obj, created = Budget.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget_obj)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'BUDGET_UPDATED', f'Limit: {budget_obj.monthly_limit}')
            messages.success(request, 'Global budget updated.')
            return redirect('dashboard')
    else:
        form = BudgetForm(instance=budget_obj)
    return render(request, 'tracker/set_budget.html', {'form': form})


@login_required
def manage_category_budgets(request):
    user = request.user
    categories = Expense.CATEGORY_CHOICES
    for cat_code, _ in categories:
        CategoryBudget.objects.get_or_create(user=user, category=cat_code, defaults={'monthly_limit': 0})

    category_budgets = CategoryBudget.objects.filter(user=user).order_by('category')

    if request.method == 'POST':
        for budget in category_budgets:
            limit_key = f'limit_{budget.category}'
            if limit_key in request.POST:
                try:
                    new_limit = float(request.POST[limit_key])
                    budget.monthly_limit = max(0, new_limit)
                    budget.save()
                except ValueError:
                    pass
        log_audit(request.user, 'CATEGORY_BUDGETS_UPDATED')
        messages.success(request, 'Category budgets updated.')
        return redirect('manage_category_budgets')

    return render(request, 'tracker/category_budgets.html', {
        'category_budgets': category_budgets, 'categories': categories
    })


# ============================================================
# EXPORT
# ============================================================

@login_required
def export_csv(request):
    user = request.user
    now = timezone.now()
    year = request.GET.get('year')
    month = request.GET.get('month')
    category_filter = request.GET.get('category', '').strip()
    if year and month:
        try:
            year, month = int(year), int(month)
            selected_date = datetime(year, month, 1).date()
        except (ValueError, TypeError):
            selected_date = now.date().replace(day=1)
    else:
        selected_date = now.date().replace(day=1)

    expenses = Expense.objects.filter(user=user, date__year=selected_date.year, date__month=selected_date.month).order_by('-date')
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
    log_audit(request.user, 'EXPORT_CSV', f'Period: {selected_date.strftime("%Y-%m")}')
    return response


# ============================================================
# RECURRING EXPENSES (function‑based add/edit/delete/toggle)
# ============================================================

@login_required
def recurring_add(request):
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST)
        if form.is_valid():
            recurring = form.save(commit=False)
            recurring.user = request.user
            recurring.next_due = recurring.start_date
            recurring.save()
            log_audit(request.user, 'RECURRING_ADDED', f'Title: {recurring.title}')
            messages.success(request, 'Recurring expense added.')
            return redirect('recurring_list')
    else:
        form = RecurringExpenseForm()
    return render(request, 'tracker/recurring_form.html', {'form': form, 'title': 'Add Recurring Expense'})


@login_required
def recurring_edit(request, pk):
    recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST, instance=recurring)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'RECURRING_UPDATED', f'ID: {pk}')
            messages.success(request, 'Recurring expense updated.')
            return redirect('recurring_list')
    else:
        form = RecurringExpenseForm(instance=recurring)
    return render(request, 'tracker/recurring_form.html', {'form': form, 'title': 'Edit Recurring Expense'})


@login_required
def recurring_delete(request, pk):
    recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    if request.method == 'POST':
        log_audit(request.user, 'RECURRING_DELETED', f'ID: {pk}')
        recurring.delete()
        messages.success(request, 'Recurring expense deleted.')
        return redirect('recurring_list')
    return render(request, 'tracker/recurring_confirm_delete.html', {'recurring': recurring})


@login_required
def recurring_toggle(request, pk):
    recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    recurring.is_active = not recurring.is_active
    recurring.save()
    status = 'activated' if recurring.is_active else 'deactivated'
    log_audit(request.user, f'RECURRING_{status.upper()}', f'ID: {pk}')
    messages.success(request, f'Recurring expense {status}.')
    return redirect('recurring_list')


# ============================================================
# SAVINGS GOALS (function‑based add/edit/delete/detail/contribute)
# ============================================================

@login_required
def goal_add(request):
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            log_audit(request.user, 'GOAL_ADDED', f'Title: {goal.title}')
            messages.success(request, 'Savings goal created.')
            return redirect('goal_list')
    else:
        form = SavingsGoalForm()
    return render(request, 'tracker/goal_form.html', {'form': form, 'title': 'Add Savings Goal'})


@login_required
def goal_edit(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'GOAL_UPDATED', f'ID: {pk}')
            messages.success(request, 'Goal updated.')
            return redirect('goal_list')
    else:
        form = SavingsGoalForm(instance=goal)
    return render(request, 'tracker/goal_form.html', {'form': form, 'title': 'Edit Savings Goal'})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        log_audit(request.user, 'GOAL_DELETED', f'ID: {pk}')
        goal.delete()
        messages.success(request, 'Goal deleted.')
        return redirect('goal_list')
    return render(request, 'tracker/goal_confirm_delete.html', {'goal': goal})


@login_required
def goal_detail(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    contributions = goal.contributions.all().order_by('-date')
    return render(request, 'tracker/goal_detail.html', {'goal': goal, 'contributions': contributions})


@login_required
def goal_contribute(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsContributionForm(request.POST)
        if form.is_valid():
            contribution = form.save(commit=False)
            contribution.goal = goal
            contribution.save()
            goal.current_amount += contribution.amount
            if goal.current_amount >= goal.target_amount:
                goal.is_completed = True
                create_notification(
                    request.user, f"Goal Achieved: {goal.title}",
                    f"Congratulations! You've reached your savings goal of ${goal.target_amount:.2f}.",
                    'goal_achieved', f'/goals/{goal.pk}/'
                )
            goal.save()
            log_audit(request.user, 'GOAL_CONTRIBUTION', f'Goal: {goal.title}, Amount: {contribution.amount}')
            messages.success(request, f'Added ${contribution.amount} to "{goal.title}".')
            return redirect('goal_detail', pk=goal.pk)
    else:
        form = SavingsContributionForm()
    return render(request, 'tracker/goal_contribute.html', {'form': form, 'goal': goal})


# ============================================================
# INCOME (function‑based add/edit/delete)
# ============================================================

@login_required
def income_add(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            log_audit(request.user, 'INCOME_ADDED', f'Title: {income.title}, Amount: {income.amount}')
            messages.success(request, 'Income added successfully.')
            return redirect('income_list')
    else:
        form = IncomeForm()
    return render(request, 'tracker/income_form.html', {'form': form, 'title': 'Add Income'})


@login_required
def income_edit(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        form = IncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'INCOME_UPDATED', f'ID: {pk}')
            messages.success(request, 'Income updated.')
            return redirect('income_list')
    else:
        form = IncomeForm(instance=income)
    return render(request, 'tracker/income_form.html', {'form': form, 'title': 'Edit Income'})


@login_required
def income_delete(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        log_audit(request.user, 'INCOME_DELETED', f'ID: {pk}')
        income.delete()
        messages.success(request, 'Income deleted.')
        return redirect('income_list')
    return render(request, 'tracker/income_confirm_delete.html', {'income': income})


# ============================================================
# BILLS (function‑based add/edit/delete/mark paid)
# ============================================================

@login_required
def bill_add(request):
    if request.method == 'POST':
        form = BillForm(request.POST)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.user = request.user
            bill.save()
            log_audit(request.user, 'BILL_ADDED', f'Title: {bill.title}')
            messages.success(request, 'Bill added successfully.')
            return redirect('bill_list')
    else:
        form = BillForm()
    return render(request, 'tracker/bill_form.html', {'form': form, 'title': 'Add Bill'})


@login_required
def bill_edit(request, pk):
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BillForm(request.POST, instance=bill)
        if form.is_valid():
            form.save()
            log_audit(request.user, 'BILL_UPDATED', f'ID: {pk}')
            messages.success(request, 'Bill updated.')
            return redirect('bill_list')
    else:
        form = BillForm(instance=bill)
    return render(request, 'tracker/bill_form.html', {'form': form, 'title': 'Edit Bill'})


@login_required
def bill_delete(request, pk):
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    if request.method == 'POST':
        log_audit(request.user, 'BILL_DELETED', f'ID: {pk}')
        bill.delete()
        messages.success(request, 'Bill deleted.')
        return redirect('bill_list')
    return render(request, 'tracker/bill_confirm_delete.html', {'bill': bill})


@login_required
def bill_mark_paid(request, pk):
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    if request.method == 'POST':
        bill.mark_paid_and_create_next()
        log_audit(request.user, 'BILL_MARKED_PAID', f'Title: {bill.title}')
        messages.success(request, f'Bill "{bill.title}" marked as paid.')
        return redirect('bill_list')
    return render(request, 'tracker/bill_mark_paid.html', {'bill': bill})


# ============================================================
# NOTIFICATIONS (function‑based mark read)
# ============================================================

@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect(notification.link) if notification.link else redirect('notification_list')


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')


# ============================================================
# REPORTS
# ============================================================

@login_required
def generate_report(request):
    user = request.user
    now = timezone.now()
    year = request.GET.get('year')
    month = request.GET.get('month')
    report_type = request.GET.get('type', 'monthly')

    if report_type == 'yearly':
        if year:
            try:
                year = int(year)
                selected_date = datetime(year, 1, 1).date()
            except (ValueError, TypeError):
                selected_date = now.date().replace(month=1, day=1)
        else:
            selected_date = now.date().replace(month=1, day=1)
        start_date = selected_date
        end_date = selected_date.replace(month=12, day=31)
        period_label = f"Year {selected_date.year}"
    else:
        if year and month:
            try:
                year, month = int(year), int(month)
                selected_date = datetime(year, month, 1).date()
            except (ValueError, TypeError):
                selected_date = now.date().replace(day=1)
        else:
            selected_date = now.date().replace(day=1)
        start_date = selected_date
        end_date = selected_date + relativedelta(day=31)
        period_label = selected_date.strftime("%B %Y")

    if report_type == 'yearly':
        income_qs = Income.objects.filter(user=user, date__year=start_date.year)
        expenses_qs = Expense.objects.filter(user=user, date__year=start_date.year)
    else:
        income_qs = Income.objects.filter(user=user, date__year=start_date.year, date__month=start_date.month)
        expenses_qs = Expense.objects.filter(user=user, date__year=start_date.year, date__month=start_date.month)

    total_income = income_qs.aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
    net_savings = total_income - total_expenses

    category_data = expenses_qs.values('category').annotate(total=Sum('amount')).order_by('-total')
    categories = [item['category'] for item in category_data]
    amounts = [float(item['total']) for item in category_data]

    category_budget_status = []
    if report_type == 'monthly':
        category_budgets = {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=user)}
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
    current_year = now.year
    years_range = range(current_year - 5, current_year + 1)
    months = [{'value': i, 'name': datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]

    context = {
        'report_type': report_type, 'period_label': period_label,
        'total_income': total_income, 'total_expenses': total_expenses, 'net_savings': net_savings,
        'categories': categories, 'amounts': amounts, 'category_budget_status': category_budget_status,
        'top_expenses': top_expenses, 'selected_year': start_date.year,
        'selected_month': start_date.month if report_type == 'monthly' else None,
        'years_range': years_range, 'months': months,
    }
    return render(request, 'tracker/report.html', context)


# ============================================================
# PROFILE & SETTINGS
# ============================================================

@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'tracker/profile.html', {'profile': profile_obj})


@login_required
def profile_edit(request):
    user = request.user
    profile_obj, _ = UserProfile.objects.get_or_create(user=user)
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile_obj)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            log_audit(request.user, 'PROFILE_UPDATED')
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=profile_obj)
    return render(request, 'tracker/profile_edit.html', {'user_form': user_form, 'profile_form': profile_form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_audit(request.user, 'PASSWORD_CHANGED')
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('profile')
    else:
        form = CustomPasswordChangeForm(user=request.user)
    return render(request, 'tracker/change_password.html', {'form': form})


@login_required
def delete_account(request):
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            user = request.user
            log_audit(user, 'ACCOUNT_DELETED')
            logout(request)
            user.delete()
            messages.success(request, 'Your account has been permanently deleted.')
            return redirect('login')
    else:
        form = DeleteAccountForm()
    return render(request, 'tracker/delete_account.html', {'form': form})


# ============================================================
# CURRENCY
# ============================================================

@login_required
def set_currency(request):
    if request.method == 'POST':
        currency_code = request.POST.get('currency')
        if currency_code:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.preferred_currency = currency_code
            profile.save()
            log_audit(request.user, f'CURRENCY_CHANGED', f'New: {currency_code}')
            messages.success(request, f'Currency changed to {currency_code}.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))