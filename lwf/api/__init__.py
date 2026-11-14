"""
The API at /api/v1/: for other systems (key in X-API-Key) and for apps used by
staff (Authorization: Bearer token from /api/v1/auth/token). Interactive
documentation at /api/v1/docs for signed-in staff.
"""
from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI
from ninja.throttling import AnonRateThrottle, AuthRateThrottle

from lwf.api import applications, integrations

api = NinjaAPI(
    title='Loan Workflow API', version='1.0', urls_namespace='api-v1',
    description='Applications, reference data, core banking, credit bureau and eKYC. '
                'Every call is logged; keys and their scopes are managed in the admin (API clients).',
    docs_decorator=staff_member_required,
    throttle=[AnonRateThrottle('30/m'), AuthRateThrottle('300/m')],
)
api.add_router('/', applications.router)
api.add_router('/auth', applications.auth_router)
api.add_router('/', integrations.router)
