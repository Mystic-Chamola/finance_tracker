from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .base import PaginatedListView
from ..models import Bill
from ..forms import BillForm

class BillListView(PaginatedListView):
    model = Bill
    template_name = 'tracker/bill_list.html'
    ordering = ['is_paid', 'due_date']

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