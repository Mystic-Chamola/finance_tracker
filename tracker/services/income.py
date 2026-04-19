import logging
from django.db import transaction, DatabaseError
from ..models import Income
from ..forms import IncomeForm
from ..audit import log_audit

logger = logging.getLogger(__name__)


class IncomeService:
    """Handles all income-related business logic."""

    def __init__(self, user):
        self.user = user

    def create(self, data):
        form = IncomeForm(data)
        if not form.is_valid():
            return None, form.errors

        try:
            with transaction.atomic():
                income = form.save(commit=False)
                income.user = self.user
                income.save()
            log_audit(self.user, 'INCOME_ADDED', f'Title: {income.title}, Amount: {income.amount}')
            return income, None
        except DatabaseError as e:
            logger.error(f"Database error creating income: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error creating income")
            return None, {'__all__': ['An unexpected error occurred.']}

    def update(self, income_id, data):
        income = Income.objects.filter(pk=income_id, user=self.user).first()
        if not income:
            return None, {'__all__': ['Income not found.']}

        form = IncomeForm(data, instance=income)
        if not form.is_valid():
            return None, form.errors

        try:
            form.save()
            log_audit(self.user, 'INCOME_UPDATED', f'ID: {income_id}')
            return income, None
        except DatabaseError as e:
            logger.error(f"Database error updating income {income_id}: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception(f"Unexpected error updating income {income_id}")
            return None, {'__all__': ['An unexpected error occurred.']}

    def delete(self, income_id):
        income = Income.objects.filter(pk=income_id, user=self.user).first()
        if not income:
            return False, 'Income not found.'

        try:
            income.delete()
            log_audit(self.user, 'INCOME_DELETED', f'ID: {income_id}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting income {income_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error deleting income {income_id}")
            return False, 'An unexpected error occurred.'

    def get_queryset(self):
        return Income.objects.filter(user=self.user).order_by('-date')