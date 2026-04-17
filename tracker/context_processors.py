from .models import Notification, UserProfile, Currency

def notifications_processor(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user, is_read=False)[:5]
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications,
        }
    return {}

def currency_processor(request):
    """Add available currencies and user's preferred currency to context."""
    currencies = Currency.objects.all().order_by('code')
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        user_currency = profile.preferred_currency if profile else 'USD'
    else:
        user_currency = 'USD'
    return {
        'available_currencies': currencies,
        'user_currency': user_currency,
    }