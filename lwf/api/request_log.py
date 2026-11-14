"""Keep a record of every API call (ApiRequestLog)."""
import time

from lwf.models import ApiRequestLog


class ApiLogMiddleware:
    prefix = '/api/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.prefix):
            return self.get_response(request)
        started = time.monotonic()
        response = self.get_response(request)
        user = getattr(request, 'api_user', None)
        ApiRequestLog.objects.create(
            client=getattr(request, 'api_client', None), user=user, method=request.method,
            path=request.path[:300], status=response.status_code, ip=request.META.get('REMOTE_ADDR'),
            duration_ms=int((time.monotonic() - started) * 1000))
        return response
