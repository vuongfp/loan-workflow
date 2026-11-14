"""Admin home page: the user's work queue and, for team admins, team workload."""
from datetime import timedelta

from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from lwf import notifications, reports
from lwf.access import accessible_tickets, user_in_groups
from lwf.models import Applicant, Officer, Ticket
from lwf.workflow import FINISHED_STATUSES

TEAM_ADMINS = ('SaleAdmin', 'CEDAdmin', 'CRAAdmin')


def dashboard_callback(request, context):
    user = request.user
    now = timezone.now()
    visible = accessible_tickets(user)
    open_visible = visible.exclude(status__in=FINISHED_STATUSES)
    mine = open_visible.filter(assigned_to=user)
    primary = Applicant.objects.filter(ticket=OuterRef('pk'), typeofapplicant=1).values('name_vn')[:1]

    counts = open_visible.aggregate(
        open=Count('pk'),
        mine=Count('pk', filter=Q(assigned_to=user)),
        overdue=Count('pk', filter=Q(assigned_to=user, due_date__lt=now)),
    )
    counts['completed_30d'] = visible.filter(status=Ticket.COMPLETE_STATUS,
                                             modified__gte=now - timedelta(days=30)).count()

    labels = dict(Ticket.STATUS_CHOICES)
    by_status = (open_visible.values('status').annotate(total=Count('pk')).order_by('status'))
    largest = max((row['total'] for row in by_status), default=0) or 1

    context.update({
        'kpis': [
            {'title': _('My open applications'), 'value': counts['mine']},
            {'title': _('Overdue (mine)'), 'value': counts['overdue'], 'alert': counts['overdue'] > 0},
            {'title': _('Open applications I can see'), 'value': counts['open']},
            {'title': _('Completed in the last 30 days'), 'value': counts['completed_30d']},
        ],
        'my_queue': (mine.select_related('loan').annotate(primary_name=Subquery(primary))
                     .order_by('due_date', 'modified')[:20]),
        'pipeline': [{'status': labels.get(row['status'], row['status']), 'total': row['total'],
                      'width': round(row['total'] * 100 / largest)} for row in by_status],
        'now': now,
        'my_officer': Officer.objects.filter(user=user).first(),
        'weekly_chart': reports.weekly_chart(user),
        'notifications': list(notifications.unread(user).select_related('ticket', 'actor')[:5]),
        'unread_count': notifications.unread(user).count(),
        'weekly_options': reports.WEEKLY_OPTIONS,
    })
    if user.is_superuser or user_in_groups(user, *TEAM_ADMINS):
        context['workload'] = (
            Officer.objects.select_related('user', 'mainteam')
            .annotate(open_count=Count('user__assigned_to', filter=~Q(
                user__assigned_to__status__in=FINISHED_STATUSES)))
            .order_by('mainteam__name', '-open_count'))
    return context
