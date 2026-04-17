import csv
import os
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
from django.conf import settings
from .models import Expense, Budget, RecurringExpense, SavingsGoal, SavingsContribution, Income, CategoryBudget, Bill, Notification, UserProfile, Currency
from .forms import (
    RegisterForm, ExpenseForm, BudgetForm, RecurringExpenseForm,
    SavingsGoalForm, SavingsContributionForm, IncomeForm, CategoryBudgetForm,
    BillForm, UserProfileForm, UserUpdateForm, CustomPasswordChangeForm, DeleteAccountForm
)
from .utils import create_notification, check_budget_alerts, check_category_budget_alerts, check_bill_reminders


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Budget.objects.create(user=user, monthly_limit=0)
            UserProfile.objects.create(user=user, preferred_currency='USD')
            messages.success(request, 'Registration successful. You can now log in.')
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()

    year = request.GET.get('year')
    month = request.GET.get('month')
    category_filter = request.GET.get('category', '').strip()

    if year and month:
        try:
            year = int(year)
            month = int(month)
            selected_date = datetime(year, month, 1).date()
        except (ValueError, TypeError):
            selected_date = now.date().replace(day=1)
    else:
        selected_date = now.date().replace(day=1)

    current_month = selected_date.month
    current_year = selected_date.year

    budget_obj, created = Budget.objects.get_or_create(user=user, defaults={'monthly_limit': 0})
    budget_limit = budget_obj.monthly_limit

    expenses_qs = Expense.objects.filter(
        user=user,
        date__year=current_year,
        date__month=current_month
    )
    if category_filter:
        expenses_qs = expenses_qs.filter(category__iexact=category_filter)

    expenses = expenses_qs.order_by('-date')
    total_spent = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

    income_qs = Income.objects.filter(
        user=user,
        date__year=current_year,
        date__month=current_month
    )
    total_income = income_qs.aggregate(total=Sum('amount'))['total'] or 0

    net_savings = total_income - total_spent
    remaining_budget = budget_limit - total_spent
    over_budget = remaining_budget < 0

    paginator = Paginator(expenses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_category_data = (
        Expense.objects.filter(
            user=user,
            date__year=current_year,
            date__month=current_month
        )
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    categories = [item['category'] for item in all_category_data]
    amounts = [float(item['total']) for item in all_category_data]

    start_date = selected_date - relativedelta(months=5)
    monthly_qs = Expense.objects.filter(user=user, date__gte=start_date)
    if category_filter:
        monthly_qs = monthly_qs.filter(category__iexact=category_filter)

    monthly_expenses = (
        monthly_qs
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    month_labels = []
    monthly_totals = []
    monthly_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in monthly_expenses}

    for i in range(5, -1, -1):
        month_date = selected_date - relativedelta(months=i)
        month_key = month_date.strftime('%Y-%m')
        month_labels.append(month_date.strftime('%b %Y'))
        monthly_totals.append(monthly_dict.get(month_key, 0))

    monthly_income_qs = Income.objects.filter(user=user, date__gte=start_date)
    monthly_income_data = (
        monthly_income_qs
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    income_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in monthly_income_data}
    monthly_income_totals = []
    for i in range(5, -1, -1):
        month_date = selected_date - relativedelta(months=i)
        month_key = month_date.strftime('%Y-%m')
        monthly_income_totals.append(income_dict.get(month_key, 0))

    daily_expenses = (
        expenses_qs
        .annotate(day=TruncDay('date'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    daily_dict = {item['day'].day: float(item['total']) for item in daily_expenses}
    days_in_month = (selected_date + relativedelta(day=31)).replace(day=1) - timedelta(days=1)
    daily_labels = list(range(1, days_in_month.day + 1))
    daily_totals = [daily_dict.get(day, 0) for day in daily_labels]

    last_year_date = selected_date - relativedelta(years=1)
    last_year_spent = Expense.objects.filter(
        user=user,
        date__year=last_year_date.year,
        date__month=last_year_date.month
    ).aggregate(total=Sum('amount'))['total'] or 0
    last_year_income = Income.objects.filter(
        user=user,
        date__year=last_year_date.year,
        date__month=last_year_date.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    forecast_months = []
    forecast_values = []
    for i in range(1, 4):
        past_date = selected_date - relativedelta(months=i)
        past_spent = Expense.objects.filter(
            user=user,
            date__year=past_date.year,
            date__month=past_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        forecast_months.append(past_date.strftime('%b %Y'))
        forecast_values.append(float(past_spent))
    forecast_next = sum(forecast_values) / len(forecast_values) if forecast_values else 0

    category_budgets = {cb.category: cb.monthly_limit for cb in CategoryBudget.objects.filter(user=user)}
    category_spending = {
        item['category']: item['total']
        for item in all_category_data
    }

    category_budget_status = []
    for cat_code, cat_name in Expense.CATEGORY_CHOICES:
        spent = float(category_spending.get(cat_code, 0))
        limit = float(category_budgets.get(cat_code, 0))
        if limit > 0:
            percentage = min(100, (spent / limit) * 100)
            remaining = limit - spent
            over = spent > limit
        else:
            percentage = 0
            remaining = 0
            over = False
        category_budget_status.append({
            'category': cat_code,
            'display': cat_name,
            'spent': spent,
            'limit': limit,
            'percentage': percentage,
            'remaining': remaining,
            'over': over,
        })

    prev_month = selected_date - relativedelta(months=1)
    next_month = selected_date + relativedelta(months=1)

    active_goals = SavingsGoal.objects.filter(user=user, is_completed=False).order_by('-created_at')[:3]

    today = now.date()
    upcoming_bills = Bill.objects.filter(
        user=user,
        is_paid=False,
        due_date__gte=today,
        due_date__lte=today + relativedelta(days=7)
    ).order_by('due_date')

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
        'prev_month': prev_month,
        'next_month': next_month,
        'category_filter': category_filter,
        'active_goals': active_goals,
        'category_budget_status': category_budget_status,
        'upcoming_bills': upcoming_bills,
        'daily_labels': daily_labels,
        'daily_totals': daily_totals,
        'last_year_spent': float(last_year_spent),
        'last_year_income': float(last_year_income),
        'last_year_month': last_year_date.strftime('%B %Y'),
        'forecast_months': forecast_months,
        'forecast_values': forecast_values,
        'forecast_next': forecast_next,
    }
    return render(request, 'tracker/dashboard.html', context)


@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
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
            messages.success(request, 'Expense updated successfully.')
            return redirect('dashboard')
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'tracker/edit_expense.html', {'form': form})


@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted.')
        return redirect('dashboard')
    return render(request, 'tracker/delete_expense.html', {'expense': expense})


@login_required
def set_budget(request):
    budget_obj, created = Budget.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget_obj)
        if form.is_valid():
            form.save()
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
        messages.success(request, 'Category budgets updated.')
        return redirect('manage_category_budgets')

    return render(request, 'tracker/category_budgets.html', {
        'category_budgets': category_budgets,
        'categories': categories,
    })


@login_required
def export_csv(request):
    user = request.user
    now = timezone.now()

    year = request.GET.get('year')
    month = request.GET.get('month')
    category_filter = request.GET.get('category', '').strip()

    if year and month:
        try:
            year = int(year)
            month = int(month)
            selected_date = datetime(year, month, 1).date()
        except (ValueError, TypeError):
            selected_date = now.date().replace(day=1)
    else:
        selected_date = now.date().replace(day=1)

    expenses = Expense.objects.filter(
        user=user,
        date__year=selected_date.year,
        date__month=selected_date.month
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
        writer.writerow([
            expense.title,
            str(expense.amount),
            expense.category,
            expense.date.strftime('%Y-%m-%d')
        ])

    return response


@login_required
def recurring_list(request):
    recurrings = RecurringExpense.objects.filter(user=request.user).order_by('-is_active', 'next_due')
    return render(request, 'tracker/recurring_list.html', {'recurrings': recurrings})


@login_required
def recurring_add(request):
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST)
        if form.is_valid():
            recurring = form.save(commit=False)
            recurring.user = request.user
            recurring.next_due = recurring.start_date
            recurring.save()
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
            messages.success(request, 'Recurring expense updated.')
            return redirect('recurring_list')
    else:
        form = RecurringExpenseForm(instance=recurring)
    return render(request, 'tracker/recurring_form.html', {'form': form, 'title': 'Edit Recurring Expense'})


@login_required
def recurring_delete(request, pk):
    recurring = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    if request.method == 'POST':
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
    messages.success(request, f'Recurring expense {status}.')
    return redirect('recurring_list')


@login_required
def goal_list(request):
    goals = SavingsGoal.objects.filter(user=request.user).order_by('-is_completed', '-created_at')
    return render(request, 'tracker/goal_list.html', {'goals': goals})


@login_required
def goal_add(request):
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
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
            messages.success(request, 'Goal updated.')
            return redirect('goal_list')
    else:
        form = SavingsGoalForm(instance=goal)
    return render(request, 'tracker/goal_form.html', {'form': form, 'title': 'Edit Savings Goal'})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
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
                    request.user,
                    f"Goal Achieved: {goal.title}",
                    f"Congratulations! You've reached your savings goal of ${goal.target_amount:.2f}.",
                    'goal_achieved',
                    f'/goals/{goal.pk}/'
                )
            goal.save()
            messages.success(request, f'Added ${contribution.amount} to "{goal.title}".')
            return redirect('goal_detail', pk=goal.pk)
    else:
        form = SavingsContributionForm()
    return render(request, 'tracker/goal_contribute.html', {'form': form, 'goal': goal})


@login_required
def income_list(request):
    incomes = Income.objects.filter(user=request.user).order_by('-date')
    return render(request, 'tracker/income_list.html', {'incomes': incomes})


@login_required
def income_add(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
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
            messages.success(request, 'Income updated.')
            return redirect('income_list')
    else:
        form = IncomeForm(instance=income)
    return render(request, 'tracker/income_form.html', {'form': form, 'title': 'Edit Income'})


@login_required
def income_delete(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        income.delete()
        messages.success(request, 'Income deleted.')
        return redirect('income_list')
    return render(request, 'tracker/income_confirm_delete.html', {'income': income})


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
                year = int(year)
                month = int(month)
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

    category_data = (
        expenses_qs.values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
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
                percentage = 0
                remaining = 0
                over = False
            category_budget_status.append({
                'category': cat_code,
                'display': cat_name,
                'spent': spent,
                'limit': limit,
                'percentage': percentage,
                'remaining': remaining,
                'over': over,
            })

    top_expenses = expenses_qs.order_by('-amount')[:10]

    current_year = now.year
    years_range = range(current_year - 5, current_year + 1)

    months = [
        {'value': 1, 'name': 'January'},
        {'value': 2, 'name': 'February'},
        {'value': 3, 'name': 'March'},
        {'value': 4, 'name': 'April'},
        {'value': 5, 'name': 'May'},
        {'value': 6, 'name': 'June'},
        {'value': 7, 'name': 'July'},
        {'value': 8, 'name': 'August'},
        {'value': 9, 'name': 'September'},
        {'value': 10, 'name': 'October'},
        {'value': 11, 'name': 'November'},
        {'value': 12, 'name': 'December'},
    ]

    context = {
        'report_type': report_type,
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_savings': net_savings,
        'categories': categories,
        'amounts': amounts,
        'category_budget_status': category_budget_status,
        'top_expenses': top_expenses,
        'selected_year': start_date.year,
        'selected_month': start_date.month if report_type == 'monthly' else None,
        'years_range': years_range,
        'months': months,
    }
    return render(request, 'tracker/report.html', context)


# ----- Bill Reminders Views -----
@login_required
def bill_list(request):
    bills = Bill.objects.filter(user=request.user).order_by('is_paid', 'due_date')
    return render(request, 'tracker/bill_list.html', {'bills': bills})


@login_required
def bill_add(request):
    if request.method == 'POST':
        form = BillForm(request.POST)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.user = request.user
            bill.save()
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
            messages.success(request, 'Bill updated.')
            return redirect('bill_list')
    else:
        form = BillForm(instance=bill)
    return render(request, 'tracker/bill_form.html', {'form': form, 'title': 'Edit Bill'})


@login_required
def bill_delete(request, pk):
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    if request.method == 'POST':
        bill.delete()
        messages.success(request, 'Bill deleted.')
        return redirect('bill_list')
    return render(request, 'tracker/bill_confirm_delete.html', {'bill': bill})


@login_required
def bill_mark_paid(request, pk):
    bill = get_object_or_404(Bill, pk=pk, user=request.user)
    if request.method == 'POST':
        bill.mark_paid_and_create_next()
        messages.success(request, f'Bill "{bill.title}" marked as paid.')
        return redirect('bill_list')
    return render(request, 'tracker/bill_mark_paid.html', {'bill': bill})


# ----- Notifications Views -----
@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(request, 'tracker/notification_list.html', {'notifications': notifications})


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('notification_list')


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notification_list')


# ----- User Profile & Settings -----
@login_required
def profile(request):
    user = request.user
    profile_obj, created = UserProfile.objects.get_or_create(user=user)
    return render(request, 'tracker/profile.html', {'profile': profile_obj})


@login_required
def profile_edit(request):
    user = request.user
    profile_obj, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile_obj)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=profile_obj)

    return render(request, 'tracker/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
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
            logout(request)
            user.delete()
            messages.success(request, 'Your account has been permanently deleted.')
            return redirect('login')
    else:
        form = DeleteAccountForm()
    return render(request, 'tracker/delete_account.html', {'form': form})


# ----- Currency Quick Change -----
@login_required
def set_currency(request):
    if request.method == 'POST':
        currency_code = request.POST.get('currency')
        if currency_code:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.preferred_currency = currency_code
            profile.save()
            messages.success(request, f'Currency changed to {currency_code}.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))