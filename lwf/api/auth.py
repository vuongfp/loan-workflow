"""
Who is calling the API: another system with a key (X-API-Key) or a person using
an app with a sign-in token (Authorization: Bearer). Scopes limit systems;
people act with their own rights in the application.
"""
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import APIKeyHeader, HttpBearer

from lwf.access import accessible_tickets
from lwf.models import ApiClient, ApiToken, Ticket

# What a person's app may do; the applications are still only those the person may see.
USER_SCOPES = {ApiClient.APPLICATIONS_READ, ApiClient.PERSONAL_DATA, ApiClient.REFERENCE_READ, ApiClient.EKYC}


def client_ip(request):
    return request.META.get('REMOTE_ADDR')


class KeyAuth(APIKeyHeader):
    param_name = 'X-API-Key'

    def authenticate(self, request, key):
        client = ApiClient.from_key(key or '')
        if client is None or not client.allows_ip(client_ip(request)):
            return None
        ApiClient.objects.filter(pk=client.pk).update(last_used=timezone.now())
        request.api_client = client
        return client


class TokenAuth(HttpBearer):
    def authenticate(self, request, token):
        found = ApiToken.from_key(token or '')
        if found is None:
            return None
        ApiToken.objects.filter(pk=found.pk).update(last_used=timezone.now())
        request.api_user = found.user
        return found


KEY_OR_TOKEN = [KeyAuth(), TokenAuth()]


def require(request, scope):
    """Stop with 403 unless the caller may use `scope`."""
    if isinstance(request.auth, ApiClient):
        allowed = request.auth.has_scope(scope)
    else:
        allowed = scope in USER_SCOPES
    if not allowed:
        raise HttpError(403, 'This key may not do this (scope %s).' % scope)


def may_see_personal_data(request):
    if isinstance(request.auth, ApiClient):
        return request.auth.has_scope(ApiClient.PERSONAL_DATA) or request.auth.has_scope(ApiClient.CORE_BANKING)
    return True


def visible_tickets(request):
    """Systems with the scope see every application; a person sees what the app's own rules allow."""
    if isinstance(request.auth, ApiClient):
        return Ticket.objects.all()
    return accessible_tickets(request.auth.user)


def caller_name(request):
    if isinstance(request.auth, ApiClient):
        return 'api:%s' % request.auth.name
    return 'app:%s' % request.auth.user.username
