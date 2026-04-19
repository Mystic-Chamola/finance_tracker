import logging
from django.db import transaction, DatabaseError
from ..models import Bill
from ..forms import BillForm
from ..audit import log_audit

logger = logging.getLogger(__name__)


class BillService:
    def __init__(self, user):
        self.user = user

    def create(self, data):
        form = BillForm(data)
        if not form.is_valid():
            return None, form.errors

        try:
            with transaction.atomic():
                bill = form.save(commit=False)
                bill.user = self.user
                bill.save()
            log_audit(self.user, 'BILL_ADDED', f'Title: {bill.title}')
            return bill, None
        except DatabaseError as e:
            logger.error(f"Database error creating bill: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error creating bill")
            return None, {'__all__': ['An unexpected error occurred.']}

    def update(self, bill_id, data):
        bill = Bill.objects.filter(pk=bill_id, user=self.user).first()
        if not bill:
            return None, {'__all__': ['Bill not found.']}

        form = BillForm(data, instance=bill)
        if not form.is_valid():
            return None, form.errors

        try:
            form.save()
            log_audit(self.user, 'BILL_UPDATED', f'ID: {bill_id}')
            return bill, None
        except DatabaseError as e:
            logger.error(f"Database error updating bill {bill_id}: {e}")
            return None, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception(f"Unexpected error updating bill {bill_id}")
            return None, {'__all__': ['An unexpected error occurred.']}

    def delete(self, bill_id):
        bill = Bill.objects.filter(pk=bill_id, user=self.user).first()
        if not bill:
            return False, 'Bill not found.'

        try:
            bill.delete()
            log_audit(self.user, 'BILL_DELETED', f'ID: {bill_id}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting bill {bill_id}: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception(f"Unexpected error deleting bill {bill_id}")
            return False, 'An unexpected error occurred.'

    def mark_paid(self, bill_id):
        bill = Bill.objects.filter(pk=bill_id, user=self.user).first()
        if not bill:
            return False, 'Bill not found.'

        try:
            bill.mark_paid_and_create_next()
            log_audit(self.user, 'BILL_MARKED_PAID', f'Title: {bill.title}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error marking bill paid: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception("Unexpected error marking bill paid")
            return False, 'An unexpected error occurred.'

    def get_queryset(self):
        return Bill.objects.filter(user=self.user).order_by('is_paid', 'due_date')