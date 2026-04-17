from django import template
from django.utils.safestring import mark_safe
from ..models import Currency

register = template.Library()

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'CAD': 'C$',
    'AUD': 'A$',
    'INR': '₹',
    'CNY': '¥',
    'KES': 'KSh',  # Kenyan Shilling
}

@register.filter
def format_currency(amount, currency_code):
    """Convert amount from USD to target currency and format with symbol."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return amount

    symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    if currency_code == 'USD':
        converted = amount
    else:
        try:
            currency = Currency.objects.get(code=currency_code)
            converted = amount / float(currency.rate_to_usd)
        except Currency.DoesNotExist:
            converted = amount

    return mark_safe(f"{symbol}{converted:,.2f}")