"""In-app notifications: created by the workflow and the due-date reminders, read in the admin."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from lwf.models import Notification, Ticket


def notify(user, ticket, kind, actor=None, status=None, due_date=None):
    if user is None or (actor is not None and user.pk == actor.pk):
        return None     # nobody to tell, or people's own actions
    return Notification.objects.create(user=user, ticket=ticket, kind=kind, actor=actor, status=status,
                                       due_date=due_date)


def unread(user):
    return Notification.objects.filter(user=user, read_at=None)


def badge(request):
    """Unread count for the sidebar (Unfold badge callback); empty when none."""
    user = request.user
    count = unread(user).count() if user.is_authenticated else 0
    return count or None


def mark_read(user, notifications=None):
    queryset = notifications if notifications is not None else Notification.objects.filter(user=user)
    return queryset.filter(user=user, read_at=None).update(read_at=timezone.now())


def send_due_reminders(now=None):
    """One reminder per due date: due within a day, then overdue. Returns how many were created."""
    from lwf.workflow import FINISHED_STATUSES

    now = now or timezone.now()
    created = 0
    open_tickets = (Ticket.objects.exclude(status__in=FINISHED_STATUSES)
                    .exclude(assigned_to=None).exclude(due_date=None))
    for kind, condition in ((Notification.OVERDUE, Q(due_date__lt=now)),
                            (Notification.DUE_SOON, Q(due_date__gte=now, due_date__lt=now + timedelta(days=1)))):
        for ticket in open_tickets.filter(condition).select_related('assigned_to'):
            already = Notification.objects.filter(user=ticket.assigned_to, ticket=ticket, kind=kind,
                                                  due_date=ticket.due_date).exists()
            if not already:
                notify(ticket.assigned_to, ticket, kind, due_date=ticket.due_date)
                created += 1
    return created
