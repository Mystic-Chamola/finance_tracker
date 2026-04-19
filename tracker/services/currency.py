import logging
from django.db import DatabaseError
from ..models import UserProfile, Currency
from ..audit import log_audit

logger = logging.getLogger(__name__)


class CurrencyService:
    def __init__(self, user):
        self.user = user

    def set_currency(self, currency_code):
        try:
            profile, _ = UserProfile.objects.get_or_create(user=self.user)
            profile.preferred_currency = currency_code
            profile.save()
            log_audit(self.user, 'CURRENCY_CHANGED', f'New: {currency_code}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error changing currency: {e}")
            return False, 'A database error occurred.'
        except Exception as e:
            logger.exception("Unexpected error changing currency")
            return False, 'An unexpected error occurred.'

    def get_available_currencies(self):
        return Currency.objects.all().order_by('code')

    def get_user_currency(self):
        profile = UserProfile.objects.filter(user=self.user).first()
        return profile.preferred_currency if profile else 'USD'