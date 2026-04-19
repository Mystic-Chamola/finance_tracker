import logging
from django.db import transaction, DatabaseError
from ..models import Expense
from ..forms import ExpenseForm
from ..audit import log_audit
from ..analytics import track_event

logger = logging.getLogger(__name__)


class ExpenseService:
    """Handles all expense-related business logic."""

    def __init__(self, user):
        self.user = user

    def create(self, data):
        """Create a new expense."""
        form = ExpenseForm(data)
        if not form.is_valid():
            return None, form.errors

        try:
            with transaction.atomic():
                expense = form.save(commit=False)
                expense.user = self.user
                expense.save()
            log_audit(self.user, 'EXPENSE_ADDED', f'Title: {expense.title}, Amount: {expense.amount}')
            track_event('expense_created')
            return expense, None
        except DatabaseError as e:
            logger.error(f"Database error creating expense: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error creating expense")
            return None, {'__all__': ['An unexpected error occurred.']}

    def update(self, expense_id, data):
        """Update an existing expense."""
        expense = Expense.objects.filter(pk=expense_id, user=self.user).first()
        if not expense:
            return None, {'__all__': ['Expense not found.']}

        form = ExpenseForm(data, instance=expense)
        if not form.is_valid():
            return None, form.errors

        try:
            form.save()
            log_audit(self.user, 'EXPENSE_UPDATED', f'ID: {expense_id}')
            return expense, None
        except DatabaseError as e:
            logger.error(f"Database error updating expense {expense_id}: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception(f"Unexpected error updating expense {expense_id}")
            return None, {'__all__': ['An unexpected error occurred.']}

    def delete(self, expense_id):
        """Delete an expense."""
        expense = Expense.objects.filter(pk=expense_id, user=self.user).first()
        if not expense:
            return False, 'Expense not found.'

        try:
            expense.delete()
            log_audit(self.user, 'EXPENSE_DELETED', f'ID: {expense_id}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting expense {expense_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error deleting expense {expense_id}")
            return False, 'An unexpected error occurred.'

    def get_queryset(self, year=None, month=None, category_filter=None):
        """Return filtered expense queryset."""
        qs = Expense.objects.filter(user=self.user).select_related('recurring_source')
        if year and month:
            qs = qs.filter(date__year=year, date__month=month)
        if category_filter:
            qs = qs.filter(category__iexact=category_filter)
        return qs.order_by('-date')