"""
Background work (django.tasks). The default ImmediateBackend runs a task when
it is enqueued; a queue backend can be configured in TASKS without code changes.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.tasks import task
from django.urls import reverse

logger = logging.getLogger(__name__)


@task
def notify_assignee(ticket_id, user_id):
    """Email the new handler of an application. Mail errors are logged, never raised."""
    from lwf.models import Ticket

    ticket = Ticket.objects.get(pk=ticket_id)
    user = get_user_model().objects.get(pk=user_id)
    link = 'http://%s%s' % (Site.objects.get_current().domain, reverse('admin:lwf_ticket_change', args=[ticket_id]))
    subject = 'Loan application %s: %s' % (ticket.title, ticket.get_status_display())
    body = ('Loan application %s is now with you (%s).\n\nOpen it: %s\n'
            % (ticket.title, ticket.get_status_display(), link))
    try:
        send_mail(subject, body, None, [user.email])
    except Exception:
        logger.exception('Could not email %s about application %s', user.email, ticket.title)
