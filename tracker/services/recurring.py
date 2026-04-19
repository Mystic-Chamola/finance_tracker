import logging
from django.db import transaction, DatabaseError
from ..models import RecurringExpense
from ..forms import RecurringExpenseForm
from ..audit import log_audit

logger = logging.getLogger(__name__)


class RecurringService:
    def __init__(self, user):
        self.user = user

    def create(self, data):
        form = RecurringExpenseForm(data)
        if not form.is_valid():
            return None, form.errors

        try:
            with transaction.atomic():
                recurring = form.save(commit=False)
                recurring.user = self.user
                recurring.next_due = recurring.start_date
                recurring.save()
            log_audit(self.user, 'RECURRING_ADDED', f'Title: {recurring.title}')
            return recurring, None
        except DatabaseError as e:
            logger.error(f"Database error creating recurring: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error creating recurring")
            return None, {'__all__': ['An unexpected error occurred.']}

    def update(self, recurring_id, data):
        recurring = RecurringExpense.objects.filter(pk=recurring_id, user=self.user).first()
        if not recurring:
            return None, {'__all__': ['Recurring expense not found.']}

        form = RecurringExpenseForm(data, instance=recurring)
        if not form.is_valid():
            return None, form.errors

        try:
            form.save()
            log_audit(self.user, 'RECURRING_UPDATED', f'ID: {recurring_id}')
            return recurring, None
        except DatabaseError as e:
            logger.error(f"Database error updating recurring {recurring_id}: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception(f"Unexpected error updating recurring {recurring_id}")
            return None, {'__all__': ['An unexpected error occurred.']}

    def delete(self, recurring_id):
        recurring = RecurringExpense.objects.filter(pk=recurring_id, user=self.user).first()
        if not recurring:
            return False, 'Recurring expense not found.'

        try:
            recurring.delete()
            log_audit(self.user, 'RECURRING_DELETED', f'ID: {recurring_id}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting recurring {recurring_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error deleting recurring {recurring_id}")
            return False, 'An unexpected error occurred.'

    def toggle(self, recurring_id):
        recurring = RecurringExpense.objects.filter(pk=recurring_id, user=self.user).first()
        if not recurring:
            return False, 'Recurring expense not found.'

        try:
            recurring.is_active = not recurring.is_active
            recurring.save()
            status = 'activated' if recurring.is_active else 'deactivated'
            log_audit(self.user, f'RECURRING_{status.upper()}', f'ID: {recurring_id}')
            return True, status
        except DatabaseError as e:
            logger.error(f"Database error toggling recurring {recurring_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error toggling recurring {recurring_id}")
            return False, 'An unexpected error occurred.'

    def get_queryset(self):
        return RecurringExpense.objects.filter(user=self.user).order_by('-is_active', 'next_due')