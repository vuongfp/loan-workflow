"""
/api-demo/: a page that plays a partner system (with an API key) or the staff mobile app (signed in)
looking up a customer's loans through the API, and shows each request and response as it goes.
It calls the real API from the browser, so the key, scopes, masking and logging all apply.
"""
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import render
from django.utils.translation import gettext as _

from lwf.models import Applicant, Ticket


def samples():
    """A few customers worth looking up, one of each kind. Their ID numbers show on the page: demo data only."""
    borrowers = Applicant.objects.filter(typeofapplicant=1).exclude(cid='').exclude(cid__isnull=True)
    picks, seen = [], set()

    def add(applicant, note):
        if applicant and applicant.cid not in seen:
            seen.add(applicant.cid)
            picks.append({'name': applicant.name_vn, 'id_number': applicant.cid, 'note': note})

    repeated = (Applicant.objects.values('cid').annotate(n=Count('ticket', distinct=True)).filter(n__gt=1)
                .exclude(cid='').order_by('-n').first())
    if repeated:
        add(borrowers.filter(cid=repeated['cid']).first(), _('Two applications'))
    add(borrowers.filter(ticket__status=Ticket.COMPLETE_STATUS, ticket__disbursements__isnull=False)
        .order_by('-ticket__modified').first(), _('Disbursed'))
    add(borrowers.filter(ticket__status=Ticket.DISBURSEMENT_STATUS).first(), _('Waiting for disbursement'))
    add(borrowers.filter(ticket__status=Ticket.APPROVER1_STATUS).first(), _('Being approved'))
    add(borrowers.filter(ticket__status=Ticket.REJECT_STATUS).first(), _('Rejected'))
    return picks


@staff_member_required
def api_demo(request):
    texts = {
        'stage': {'in_progress': _('In progress'), 'completed': _('Completed'), 'rejected': _('Rejected'),
                  'closed': _('Closed')},
        'errors': {
            '401': _('The key or sign-in is not valid (wrong, expired, turned off, or not allowed from this address).'),
            '403': _('This key may not read applications: give it the "Read applications" scope.'),
            '404': _('No loan application for this ID number, or none this caller may see.'),
            '422': _('Enter an ID number of 6 to 20 characters.'),
            '429': _('Too many calls in a minute: wait a moment and try again.'),
            'network': _('The server could not be reached.'),
            'other': _('The server answered with an error.'),
        },
        'need_key': _('Enter an API key first.'),
        'need_sign_in': _('Sign in first.'),
        'sign_in_failed': _('Wrong username or password, or the account may not use the app.'),
        'signed_in_as': _('Signed in as %(name)s; the token is valid until %(time)s.'),
        'masked': _('Masked: this key may not read personal data'),
        'months': _('%(n)s months'),
        'none': _('No disbursement yet'),
        'of': _('of'),
    }
    return render(request, 'lwf/api_demo.html', {
        'texts': texts,
        'samples': samples() if settings.LWF_API_DEMO_SAMPLES else [],
        'show_samples': settings.LWF_API_DEMO_SAMPLES,
    })
