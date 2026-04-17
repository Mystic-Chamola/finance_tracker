from django import forms

class PositiveAmountFormMixin:
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount < 0:
            raise forms.ValidationError('Amount cannot be negative.')
        return amount

class PositiveLimitFormMixin:
    def clean_monthly_limit(self):
        limit = self.cleaned_data.get('monthly_limit')
        if limit is not None and limit < 0:
            raise forms.ValidationError('Budget limit cannot be negative.')
        return limit