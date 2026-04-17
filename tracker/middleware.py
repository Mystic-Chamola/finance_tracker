import time
import logging

logger = logging.getLogger(__name__)

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