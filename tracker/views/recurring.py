from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .base import PaginatedListView
from ..models import RecurringExpense
from ..forms import RecurringExpenseForm

class RecurringListView(PaginatedListView):
    model = RecurringExpense
    template_name = 'tracker/recurring_list.html'
    ordering = ['-is_active', 'next_due']

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