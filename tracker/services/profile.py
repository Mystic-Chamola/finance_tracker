import logging
from django.db import transaction, DatabaseError
from django.contrib.auth import update_session_auth_hash
from ..models import UserProfile
from ..forms import UserUpdateForm, UserProfileForm, CustomPasswordChangeForm, DeleteAccountForm
from ..audit import log_audit

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, user):
        self.user = user

    def get_profile(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        return profile

    def update_profile(self, user_data, profile_data, files=None):
        user_form = UserUpdateForm(user_data, instance=self.user)
        profile_form = UserProfileForm(profile_data, files, instance=self.get_profile())

        if not (user_form.is_valid() and profile_form.is_valid()):
            errors = {**user_form.errors, **profile_form.errors}
            return False, errors

        try:
            with transaction.atomic():
                user_form.save()
                profile_form.save()
            log_audit(self.user, 'PROFILE_UPDATED')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error updating profile: {e}")
            return False, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error updating profile")
            return False, {'__all__': ['An unexpected error occurred.']}

    def change_password(self, data):
        form = CustomPasswordChangeForm(user=self.user, data=data)
        if not form.is_valid():
            return False, form.errors

        try:
            user = form.save()
            update_session_auth_hash(None, user)  # request will be passed from view
            log_audit(self.user, 'PASSWORD_CHANGED')
            return True, None
        except Exception as e:
            logger.exception("Error changing password")
            return False, {'__all__': ['An error occurred.']}

    def delete_account(self, data, request):
        form = DeleteAccountForm(data)
        if not form.is_valid():
            return False, form.errors

        try:
            log_audit(self.user, 'ACCOUNT_DELETED')
            from django.contrib.auth import logout
            logout(request)
            self.user.delete()
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error deleting account: {e}")
            return False, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error deleting account")
            return False, {'__all__': ['An unexpected error occurred.']}