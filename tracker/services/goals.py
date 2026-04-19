import logging
from django.db import transaction, DatabaseError
from ..models import SavingsGoal, SavingsContribution
from ..forms import SavingsGoalForm, SavingsContributionForm
from ..utils import create_notification
from ..audit import log_audit

logger = logging.getLogger(__name__)


class GoalService:
    def __init__(self, user):
        self.user = user

    def create(self, data):
        form = SavingsGoalForm(data)
        if not form.is_valid():
            return None, form.errors

        try:
            with transaction.atomic():
                goal = form.save(commit=False)
                goal.user = self.user
                goal.save()
            log_audit(self.user, 'GOAL_ADDED', f'Title: {goal.title}')
            return goal, None
        except DatabaseError as e:
            logger.error(f"Database error creating goal: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error creating goal")
            return None, {'__all__': ['An unexpected error occurred.']}

    def update(self, goal_id, data):
        goal = SavingsGoal.objects.filter(pk=goal_id, user=self.user).first()
        if not goal:
            return None, {'__all__': ['Goal not found.']}

        form = SavingsGoalForm(data, instance=goal)
        if not form.is_valid():
            return None, form.errors

        try:
            form.save()
            log_audit(self.user, 'GOAL_UPDATED', f'ID: {goal_id}')
            return goal, None
        except DatabaseError as e:
            logger.error(f"Database error updating goal {goal_id}: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception(f"Unexpected error updating goal {goal_id}")
            return None, {'__all__': ['An unexpected error occurred.']}

    def delete(self, goal_id):
        goal = SavingsGoal.objects.filter(pk=goal_id, user=self.user).first()
        if not goal:
            return False, 'Goal not found.'

        try:
            goal.delete()
            log_audit(self.user, 'GOAL_DELETED', f'ID: {goal_id}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting goal {goal_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error deleting goal {goal_id}")
            return False, 'An unexpected error occurred.'

    def contribute(self, goal_id, data):
        goal = SavingsGoal.objects.filter(pk=goal_id, user=self.user).first()
        if not goal:
            return False, 'Goal not found.'

        form = SavingsContributionForm(data)
        if not form.is_valid():
            return False, form.errors

        try:
            with transaction.atomic():
                contribution = form.save(commit=False)
                contribution.goal = goal
                contribution.save()
                goal.current_amount += contribution.amount
                if goal.current_amount >= goal.target_amount:
                    goal.is_completed = True
                    create_notification(
                        self.user,
                        f"Goal Achieved: {goal.title}",
                        f"Congratulations! You've reached your savings goal of ${goal.target_amount:.2f}.",
                        'goal_achieved',
                        f'/goals/{goal.pk}/'
                    )
                goal.save()
            log_audit(self.user, 'GOAL_CONTRIBUTION', f'Goal: {goal.title}, Amount: {contribution.amount}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error adding contribution: {e}")
            return False, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error adding contribution")
            return False, {'__all__': ['An unexpected error occurred.']}

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.user).order_by('-is_completed', '-created_at')