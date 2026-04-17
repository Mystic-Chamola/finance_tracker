from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .base import PaginatedListView
from ..models import SavingsGoal, SavingsContribution
from ..forms import SavingsGoalForm, SavingsContributionForm
from ..utils import create_notification

class GoalListView(PaginatedListView):
    model = SavingsGoal
    template_name = 'tracker/goal_list.html'
    ordering = ['-is_completed', '-created_at']

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