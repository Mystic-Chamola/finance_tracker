from django.utils import timezone
from django.db.models import F
from .models import DailyAnalytics


def track_event(event_type):
    """Increment a specific event counter for today."""
    today = timezone.now().date()
    DailyAnalytics.objects.get_or_create(date=today)

    field_map = {
        'expense_created': 'expenses_created',
        'income_created': 'income_created',
        'bill_created': 'bills_created',
        'goal_created': 'goals_created',
        'report_generated': 'reports_generated',
        'api_call': 'api_calls',
    }

    field = field_map.get(event_type)
    if field:
        DailyAnalytics.objects.filter(date=today).update(
            **{field: F(field) + 1}
        )