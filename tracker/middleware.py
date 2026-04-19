import time
import logging
from django.utils import timezone
from django.db.models import F
from .models import DailyAnalytics

logger = logging.getLogger(__name__)


class AnalyticsMiddleware:
    """Track daily active users and request counts."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and not request.path.startswith('/static/'):
            today = timezone.now().date()
            DailyAnalytics.objects.get_or_create(date=today)

            # Increment total requests
            DailyAnalytics.objects.filter(date=today).update(
                total_requests=F('total_requests') + 1
            )

            # Track unique daily active users using cache
            from django.core.cache import cache
            cache_key = f"dau_{today}_{request.user.id}"
            if not cache.get(cache_key):
                cache.set(cache_key, True, 86400)  # 24 hours
                DailyAnalytics.objects.filter(date=today).update(
                    active_users=F('active_users') + 1
                )

        return response


class PerformanceMonitoringMiddleware:
    """Log slow requests (over 1 second) for performance analysis."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        if duration > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.path} took {duration:.2f}s",
                extra={
                    'request': request,
                    'duration': duration,
                    'user': request.user.username if request.user.is_authenticated else 'anonymous',
                }
            )
        return response


class ExceptionLoggingMiddleware:
    """Log unhandled exceptions to file."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        logger.exception(f"Unhandled exception on {request.path}: {exception}")
        return None