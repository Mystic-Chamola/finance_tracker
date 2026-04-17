from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .base import PaginatedListView
from ..models import Income
from ..forms import IncomeForm

class IncomeListView(PaginatedListView):
    model = Income
    template_name = 'tracker/income_list.html'
    ordering = ['-date']

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