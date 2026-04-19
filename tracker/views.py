import csv
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.core.paginator import Paginator
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django_ratelimit.decorators import ratelimit

from .models import (
    Expense, Income, Bill, RecurringExpense, SavingsGoal, Notification, UserProfile, Currency
)
from .forms import (
    RegisterForm, ExpenseForm, RecurringExpenseForm, SavingsGoalForm,
    SavingsContributionForm, IncomeForm, BillForm
)
from .services import (
    DashboardService, ExpenseService, IncomeService, BillService,
    GoalService, RecurringService, BudgetService, NotificationService,
    ReportService, ProfileService, CurrencyService
)
from .audit import log_audit

logger = logging.getLogger(__name__)


# ============================================================
# CUSTOM ERROR HANDLERS
# ============================================================

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '500.html', status=500)

def custom_403(request, exception):
    return render(request, '403.html', status=403)


# ============================================================
# BASE CLASS FOR PAGINATED LIST VIEWS
# ============================================================

class PaginatedListView(LoginRequiredMixin, ListView):
    paginate_by = 20
    context_object_name = 'page_obj'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


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
# AUTHENTICATION
# ============================================================

@ratelimit(key='ip', rate='5/m', block=True)
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # Additional setup could be moved to a service if desired
                log_audit(user, 'USER_REGISTERED', f'Email: {user.email}')
                messages.success(request, 'Registration successful. You can now log in.')
                return redirect('login')
            except Exception as e:
                logger.exception("Unexpected error during registration")
                messages.error(request, 'An unexpected error occurred. Please try again.')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


# ============================================================
# DASHBOARD (Thin Orchestrator)
# ============================================================

@login_required
def dashboard(request):
    try:
        user = request.user
        year = request.GET.get('year')
        month = request.GET.get('month')
        category_filter = request.GET.get('category', '').strip()

        service = DashboardService(user)
        selected_date = service.get_selected_date(year, month)
        current_year, current_month = selected_date.year, selected_date.month

        budget_limit = service.get_budget()
        category_budgets = service.get_category_budgets()

        total_spent, total_income = service.get_monthly_totals(current_year, current_month)
        net_savings = total_income - total_spent
        remaining_budget = budget_limit - total_spent
        over_budget = remaining_budget < 0

        # Expenses with pagination
        expense_qs = Expense.objects.filter(
            user=user, date__year=current_year, date__month=current_month
        ).select_related('recurring_source')
        if category_filter:
            expense_qs = expense_qs.filter(category__iexact=category_filter)
        paginator = Paginator(expense_qs.order_by('-date'), 10)
        page_obj = paginator.get_page(request.GET.get('page'))

        # Category breakdown
        categories, amounts, category_spending = service.get_category_breakdown(
            current_year, current_month, category_filter
        )

        # Monthly trends
        month_labels, monthly_totals, monthly_income_totals = service.get_monthly_trends(
            selected_date, category_filter=category_filter
        )

        # Daily spending
        daily_labels, daily_totals = service.get_daily_spending(
            current_year, current_month, category_filter
        )

        # Year‑over‑year
        last_year_spent, last_year_income, last_year_month = service.get_year_over_year(selected_date)

        # Forecast
        forecast_months, forecast_values, forecast_next = service.get_forecast(selected_date)

        # Category budget status
        category_budget_status = service.get_category_budget_status(
            current_year, current_month, category_spending, category_budgets
        )

        active_goals = service.get_active_goals()
        upcoming_bills = service.get_upcoming_bills()

        # Trigger notifications (utils still called directly – could be moved to NotificationService)
        from .utils import check_budget_alerts, check_category_budget_alerts, check_bill_reminders
        check_budget_alerts(user, total_spent, budget_limit)
        check_category_budget_alerts(user, category_spending, category_budgets)
        check_bill_reminders(user)

        context = {
            'page_obj': page_obj,
            'total_spent': total_spent,
            'total_income': total_income,
            'net_savings': net_savings,
            'budget_limit': budget_limit,
            'remaining': remaining_budget,
            'over_budget': over_budget,
            'categories': categories,
            'amounts': amounts,
            'month_labels': month_labels,
            'monthly_totals': monthly_totals,
            'monthly_income_totals': monthly_income_totals,
            'current_month': selected_date,
            'prev_month': selected_date - relativedelta(months=1),
            'next_month': selected_date + relativedelta(months=1),
            'category_filter': category_filter,
            'active_goals': active_goals,
            'category_budget_status': category_budget_status,
            'upcoming_bills': upcoming_bills,
            'daily_labels': daily_labels,
            'daily_totals': daily_totals,
            'last_year_spent': last_year_spent,
            'last_year_income': last_year_income,
            'last_year_month': last_year_month,
            'forecast_months': forecast_months,
            'forecast_values': forecast_values,
            'forecast_next': forecast_next,
        }
        return render(request, 'tracker/dashboard.html', context)

    except Exception as e:
        logger.exception("Error rendering dashboard")
        messages.error(request, 'An error occurred while loading the dashboard. Please try again.')
        return redirect('dashboard')


# ============================================================
# EXPENSES (Using ExpenseService)
# ============================================================

@login_required
def add_expense(request):
    if request.method == 'POST':
        service = ExpenseService(request.user)
        expense, errors = service.create(request.POST)
        if expense:
            messages.success(request, 'Expense added successfully.')
            return redirect('dashboard')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        form = ExpenseForm()
    return render(request, 'tracker/add_expense.html', {'form': form})


@login_required
def edit_expense(request, pk):
    if request.method == 'POST':
        service = ExpenseService(request.user)
        expense, errors = service.update(pk, request.POST)
        if expense:
            messages.success(request, 'Expense updated successfully.')
            return redirect('dashboard')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
        form = ExpenseForm(instance=expense)
    return render(request, 'tracker/edit_expense.html', {'form': form})


@login_required
def delete_expense(request, pk):
    if request.method == 'POST':
        service = ExpenseService(request.user)
        success, error = service.delete(pk)
        if success:
            messages.success(request, 'Expense deleted.')
        else:
            messages.error(request, error)
        return redirect('dashboard')
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return render(request, 'tracker/delete_expense.html', {'expense': expense})


# ============================================================
# BUDGETS (Using BudgetService)
# ============================================================

@login_required
def set_budget(request):
    if request.method == 'POST':
        service = BudgetService(request.user)
        success, errors = service.update_global_budget(request.POST)
        if success:
            messages.success(request, 'Global budget updated.')
            return redirect('dashboard')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        budget_obj = BudgetService(request.user).get_global_budget()
        from .forms import BudgetForm
        form = BudgetForm(instance=budget_obj)
    return render(request, 'tracker/set_budget.html', {'form': form})


@login_required
def manage_category_budgets(request):
    service = BudgetService(request.user)
    if request.method == 'POST':
        success, errors = service.update_category_budgets(request.POST)
        if success:
            messages.success(request, 'Category budgets updated.')
            return redirect('manage_category_budgets')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    category_budgets = service.get_category_budgets()
    categories = Expense.CATEGORY_CHOICES
    return render(request, 'tracker/category_budgets.html', {
        'category_budgets': category_budgets,
        'categories': categories
    })


# ============================================================
# EXPORT CSV (Using ReportService)
# ============================================================

@login_required
def export_csv(request):
    service = ReportService(request.user)
    response, error = service.generate_csv(
        request.GET.get('year'),
        request.GET.get('month'),
        request.GET.get('category', '').strip()
    )
    if response:
        return response
    else:
        messages.error(request, error)
        return redirect('dashboard')


# ============================================================
# RECURRING EXPENSES (Using RecurringService)
# ============================================================

@login_required
def recurring_add(request):
    if request.method == 'POST':
        service = RecurringService(request.user)
        recurring, errors = service.create(request.POST)
        if recurring:
            messages.success(request, 'Recurring expense added.')
            return redirect('recurring_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        form = RecurringExpenseForm()
    return render(request, 'tracker/recurring_form.html', {'form': form, 'title': 'Add Recurring Expense'})


@login_required
def recurring_edit(request, pk):
    if request.method == 'POST':
        service = RecurringService(request.user)
        recurring, errors = service.update(pk, request.POST)
        if recurring:
            messages.success(request, 'Recurring expense updated.')
            return redirect('recurring_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
        form = RecurringExpenseForm(instance=recurring)
    return render(request, 'tracker/recurring_form.html', {'form': form, 'title': 'Edit Recurring Expense'})


@login_required
def recurring_delete(request, pk):
    if request.method == 'POST':
        service = RecurringService(request.user)
        success, error = service.delete(pk)
        if success:
            messages.success(request, 'Recurring expense deleted.')
        else:
            messages.error(request, error)
        return redirect('recurring_list')
    recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    return render(request, 'tracker/recurring_confirm_delete.html', {'recurring': recurring})


@login_required
def recurring_toggle(request, pk):
    service = RecurringService(request.user)
    success, status_or_error = service.toggle(pk)
    if success:
        messages.success(request, f'Recurring expense {status_or_error}.')
    else:
        messages.error(request, status_or_error)
    return redirect('recurring_list')


# ============================================================
# SAVINGS GOALS (Using GoalService)
# ============================================================

@login_required
def goal_add(request):
    if request.method == 'POST':
        service = GoalService(request.user)
        goal, errors = service.create(request.POST)
        if goal:
            messages.success(request, 'Savings goal created.')
            return redirect('goal_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        form = SavingsGoalForm()
    return render(request, 'tracker/goal_form.html', {'form': form, 'title': 'Add Savings Goal'})


@login_required
def goal_edit(request, pk):
    if request.method == 'POST':
        service = GoalService(request.user)
        goal, errors = service.update(pk, request.POST)
        if goal:
            messages.success(request, 'Goal updated.')
            return redirect('goal_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
        form = SavingsGoalForm(instance=goal)
    return render(request, 'tracker/goal_form.html', {'form': form, 'title': 'Edit Savings Goal'})


@login_required
def goal_delete(request, pk):
    if request.method == 'POST':
        service = GoalService(request.user)
        success, error = service.delete(pk)
        if success:
            messages.success(request, 'Goal deleted.')
        else:
            messages.error(request, error)
        return redirect('goal_list')
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    return render(request, 'tracker/goal_confirm_delete.html', {'goal': goal})


@login_required
def goal_detail(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    contributions = goal.contributions.all().order_by('-date')
    return render(request, 'tracker/goal_detail.html', {'goal': goal, 'contributions': contributions})


@login_required
def goal_contribute(request, pk):
    if request.method == 'POST':
        service = GoalService(request.user)
        success, errors = service.contribute(pk, request.POST)
        if success:
            messages.success(request, 'Contribution added.')
            return redirect('goal_detail', pk=pk)
        else:
            if isinstance(errors, dict):
                for field, error_list in errors.items():
                    for error in error_list:
                        msg = error if field == '__all__' else f"{field}: {error}"
                        messages.error(request, msg)
            else:
                messages.error(request, errors)
    else:
        form = SavingsContributionForm()
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    return render(request, 'tracker/goal_contribute.html', {'form': form, 'goal': goal})


# ============================================================
# INCOME (Using IncomeService)
# ============================================================

@login_required
def income_add(request):
    if request.method == 'POST':
        service = IncomeService(request.user)
        income, errors = service.create(request.POST)
        if income:
            messages.success(request, 'Income added successfully.')
            return redirect('income_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        form = IncomeForm()
    return render(request, 'tracker/income_form.html', {'form': form, 'title': 'Add Income'})


@login_required
def income_edit(request, pk):
    if request.method == 'POST':
        service = IncomeService(request.user)
        income, errors = service.update(pk, request.POST)
        if income:
            messages.success(request, 'Income updated.')
            return redirect('income_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        income = get_object_or_404(Income, pk=pk, user=request.user)
        form = IncomeForm(instance=income)
    return render(request, 'tracker/income_form.html', {'form': form, 'title': 'Edit Income'})


@login_required
def income_delete(request, pk):
    if request.method == 'POST':
        service = IncomeService(request.user)
        success, error = service.delete(pk)
        if success:
            messages.success(request, 'Income deleted.')
        else:
            messages.error(request, error)
        return redirect('income_list')
    income = get_object_or_404(Income, pk=pk, user=request.user)
    return render(request, 'tracker/income_confirm_delete.html', {'income': income})


# ============================================================
# BILLS (Using BillService)
# ============================================================

@login_required
def bill_add(request):
    if request.method == 'POST':
        service = BillService(request.user)
        bill, errors = service.create(request.POST)
        if bill:
            messages.success(request, 'Bill added successfully.')
            return redirect('bill_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        form = BillForm()
    return render(request, 'tracker/bill_form.html', {'form': form, 'title': 'Add Bill'})


@login_required
def bill_edit(request, pk):
    if request.method == 'POST':
        service = BillService(request.user)
        bill, errors = service.update(pk, request.POST)
        if bill:
            messages.success(request, 'Bill updated.')
            return redirect('bill_list')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        bill = get_object_or_404(Bill, pk=pk, user=request.user)
        form = BillForm(instance=bill)
    return render(request, 'tracker/bill_form.html', {'form': form, 'title': 'Edit Bill'})


@login_required
def bill_delete(request, pk):
    if request.method == 'POST':
        service = BillService(request.user)
        success, error = service.delete(pk)
        if success:
            messages.success(request, 'Bill deleted.')
        else:
            messages.error(request, error)
        return redirect('bill_list')
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    return render(request, 'tracker/bill_confirm_delete.html', {'bill': bill})


@login_required
def bill_mark_paid(request, pk):
    if request.method == 'POST':
        service = BillService(request.user)
        success, error = service.mark_paid(pk)
        if success:
            messages.success(request, 'Bill marked as paid.')
        else:
            messages.error(request, error)
        return redirect('bill_list')
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    return render(request, 'tracker/bill_mark_paid.html', {'bill': bill})


# ============================================================
# NOTIFICATIONS (Using NotificationService)
# ============================================================

@login_required
def mark_notification_read(request, pk):
    service = NotificationService(request.user)
    redirect_url = service.mark_read(pk)
    return redirect(redirect_url)


@login_required
def mark_all_read(request):
    service = NotificationService(request.user)
    service.mark_all_read()
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')


# ============================================================
# REPORTS (Using ReportService)
# ============================================================

@login_required
def generate_report(request):
    try:
        service = ReportService(request.user)
        context = service.get_report_context(
            request.GET.get('year'),
            request.GET.get('month'),
            request.GET.get('type', 'monthly')
        )
        return render(request, 'tracker/report.html', context)
    except Exception as e:
        logger.exception("Error generating report")
        messages.error(request, 'An error occurred while generating the report.')
        return redirect('dashboard')


# ============================================================
# PROFILE & SETTINGS (Using ProfileService)
# ============================================================

@login_required
def profile(request):
    service = ProfileService(request.user)
    profile = service.get_profile()
    return render(request, 'tracker/profile.html', {'profile': profile})


@login_required
def profile_edit(request):
    service = ProfileService(request.user)
    if request.method == 'POST':
        success, errors = service.update_profile(request.POST, request.POST, request.FILES)
        if success:
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        from .forms import UserUpdateForm, UserProfileForm
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileForm(instance=service.get_profile())
    return render(request, 'tracker/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


@login_required
def change_password(request):
    service = ProfileService(request.user)
    if request.method == 'POST':
        success, errors = service.change_password(request.POST)
        if success:
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('profile')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        from .forms import CustomPasswordChangeForm
        form = CustomPasswordChangeForm(user=request.user)
    return render(request, 'tracker/change_password.html', {'form': form})


@login_required
def delete_account(request):
    service = ProfileService(request.user)
    if request.method == 'POST':
        success, errors = service.delete_account(request.POST, request)
        if success:
            messages.success(request, 'Your account has been permanently deleted.')
            return redirect('login')
        else:
            for field, error_list in errors.items():
                for error in error_list:
                    msg = error if field == '__all__' else f"{field}: {error}"
                    messages.error(request, msg)
    else:
        from .forms import DeleteAccountForm
        form = DeleteAccountForm()
    return render(request, 'tracker/delete_account.html', {'form': form})


# ============================================================
# CURRENCY (Using CurrencyService)
# ============================================================

@login_required
def set_currency(request):
    if request.method == 'POST':
        currency_code = request.POST.get('currency')
        if currency_code:
            service = CurrencyService(request.user)
            success, error = service.set_currency(currency_code)
            if success:
                messages.success(request, f'Currency changed to {currency_code}.')
            else:
                messages.error(request, error)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))