from django.conf import settings
from django.http import HttpResponseForbidden

class AdminIPRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            ip = request.META.get('REMOTE_ADDR')
            if ip not in settings.ADMIN_IP_WHITELIST:
                return HttpResponseForbidden("Access denied.")
        return self.get_response(request)