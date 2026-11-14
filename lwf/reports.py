"""
Management reports over the applications a user may see: volumes, turnaround
time per workflow step, outcomes and rejection reasons; and the Excel export.
"""
import io
import json
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.translation import gettext as _

from lwf.access import accessible_tickets
from lwf.models import LOV, Applicant, FollowUp, Product, Ticket
from lwf.workflow import FINISHED_STATUSES

PERIODS = (30, 90, 180, 365)
# Chart colours: the brand purple and a neutral, readable in light and dark mode.
PRIMARY, SECONDARY, ACCENT = '#9333ea', '#94a3b8', '#f59e0b'
# Options merged over Unfold's chart defaults (which draw 4px bars and hide the legend).
BAR_OPTIONS = {'maxBarThickness': 40}
LEGEND = {'legend': {'display': True, 'align': 'end', 'position': 'top'}}


def _days(delta):
    return round(delta.total_seconds() / 86400, 1)


def turnaround_by_status(tickets):
    """Average and count of days spent at each status, from the workflow history."""
    entered = {t.pk: (t.created, Ticket.OPEN_STATUS) for t in tickets.only('pk', 'created')}
    spent = defaultdict(list)
    steps = (FollowUp.objects.filter(ticket__in=tickets).exclude(new_status=None)
             .order_by('ticket_id', 'date').values_list('ticket_id', 'date', 'new_status'))
    for ticket_id, date, new_status in steps:
        start, status = entered.get(ticket_id, (None, None))
        if start and status and date >= start:
            spent[status].append(date - start)
        entered[ticket_id] = (date, new_status)
    labels = dict(Ticket.STATUS_CHOICES)
    order = [code for code, _label in Ticket.STATUS_CHOICES]
    return [{'status': str(labels[code]), 'days': _days(sum(spent[code], timedelta()) / len(spent[code])),
             'count': len(spent[code])}
            for code in order if spent.get(code)]


def report(user, days=90):
    """Everything the reports page and the Excel file show, for the last `days` days."""
    now = timezone.now()
    since = now - timedelta(days=days)
    tickets = accessible_tickets(user).filter(created__gte=since)
    products = dict(Product.objects.values_list('product_code', 'product').distinct())

    monthly = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'amount': 0}))
    for row in (tickets.annotate(month=TruncMonth('created')).values('month', 'loan__product')
                .annotate(count=Count('pk'), amount=Sum('loan__loanamount')).order_by('month')):
        cell = monthly[row['month'].strftime('%m/%Y')][products.get(row['loan__product'], _('Other'))]
        cell['count'] += row['count']
        cell['amount'] += row['amount'] or 0

    reasons = dict(LOV.REJECT_CHOICES)
    rejected = (tickets.filter(status=Ticket.REJECT_STATUS).values('reject_code')
                .annotate(total=Count('pk')).order_by('-total'))
    completed = tickets.filter(status=Ticket.COMPLETE_STATUS)
    durations = [ticket.modified - ticket.created for ticket in completed.only('created', 'modified')]
    return {
        'days': days, 'since': since, 'now': now,
        'kpis': {
            'received': tickets.count(),
            'in_progress': tickets.exclude(status__in=FINISHED_STATUSES).count(),
            'completed': len(durations),
            'rejected': tickets.filter(status=Ticket.REJECT_STATUS).count(),
            'amount_completed': completed.aggregate(total=Sum('loan__loanamount'))['total'] or 0,
            'days_to_complete': _days(sum(durations, timedelta()) / len(durations)) if durations else None,
        },
        'monthly': {month: dict(by_product) for month, by_product in monthly.items()},
        'turnaround': turnaround_by_status(tickets),
        'rejections': [{'reason': str(reasons.get(row['reject_code'], _('Not given'))), 'total': row['total']}
                       for row in rejected],
        'tickets': tickets,
    }


def charts(data):
    """Chart.js data (JSON) for the reports page."""
    months = list(data['monthly'])
    product_names = sorted({name for by_product in data['monthly'].values() for name in by_product})
    palette = [PRIMARY, SECONDARY, ACCENT, '#0ea5e9', '#22c55e', '#ef4444']
    volume = {'labels': months, 'datasets': [
        {'label': name, 'data': [data['monthly'][m].get(name, {}).get('count', 0) for m in months],
         'backgroundColor': palette[i % len(palette)], 'stack': 'products'}
        for i, name in enumerate(product_names)]}
    turnaround = {'labels': [row['status'] for row in data['turnaround']], 'datasets': [
        {'label': _('Average days'), 'data': [row['days'] for row in data['turnaround']],
         'backgroundColor': PRIMARY}]}
    rejections = {'labels': [row['reason'] for row in data['rejections']], 'datasets': [
        {'label': _('Number of applications'), 'data': [row['total'] for row in data['rejections']],
         'backgroundColor': ACCENT}]}
    return {'volume': json.dumps(volume), 'turnaround': json.dumps(turnaround),
            'rejections': json.dumps(rejections),
            'volume_options': json.dumps({**BAR_OPTIONS, 'plugins': LEGEND,
                                          'scales': {'x': {'stacked': True}, 'y': {'stacked': True}}}),
            'turnaround_options': json.dumps({**BAR_OPTIONS, 'indexAxis': 'y', 'maxBarThickness': 20}),
            'bar_options': json.dumps(BAR_OPTIONS)}


WEEKLY_OPTIONS = json.dumps({'grouped': True, 'maxBarThickness': 24, 'barPercentage': 0.8, 'plugins': LEGEND})


def weekly_chart(user, weeks=8):
    """New and completed applications per week, for the dashboard."""
    since = timezone.now() - timedelta(weeks=weeks)
    visible = accessible_tickets(user)
    new = dict(visible.filter(created__gte=since).annotate(week=TruncWeek('created'))
               .values('week').annotate(total=Count('pk')).values_list('week', 'total'))
    done = dict(visible.filter(status=Ticket.COMPLETE_STATUS, modified__gte=since)
                .annotate(week=TruncWeek('modified')).values('week').annotate(total=Count('pk'))
                .values_list('week', 'total'))
    weeks_seen = sorted(set(new) | set(done))
    return json.dumps({'labels': [week.strftime('%d/%m') for week in weeks_seen], 'datasets': [
        {'label': _('New'), 'data': [new.get(week, 0) for week in weeks_seen], 'backgroundColor': SECONDARY},
        {'label': _('Completed'), 'data': [done.get(week, 0) for week in weeks_seen], 'backgroundColor': PRIMARY},
    ]})


def excel(data):
    """The report as an .xlsx file (bytes): summary, applications, turnaround, rejections."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    book = Workbook()

    def sheet(title, header, rows, first=False):
        ws = book.active if first else book.create_sheet()
        ws.title = title[:31]
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append(row)
        for index, column in enumerate(ws.columns, start=1):
            width = max(len(str(cell.value or '')) for cell in column)
            ws.column_dimensions[get_column_letter(index)].width = min(max(10, width + 2), 60)
        ws.freeze_panes = 'A2'
        return ws

    k = data['kpis']
    sheet(_('Summary'), [_('Measure'), _('Value')], [
        (_('Period'), '%s - %s' % (data['since'].strftime('%d/%m/%Y'), data['now'].strftime('%d/%m/%Y'))),
        (_('Applications received'), k['received']), (_('In progress'), k['in_progress']),
        (_('Completed'), k['completed']), (_('Rejected'), k['rejected']),
        (_('Amount completed (VND)'), k['amount_completed']),
        (_('Average days to complete'), k['days_to_complete']),
    ], first=True)

    primary = dict(Applicant.objects.filter(ticket__in=data['tickets'], typeofapplicant=1)
                   .values_list('ticket_id', 'name_vn'))
    tz = timezone.get_current_timezone()
    rows = []
    for t in data['tickets'].select_related('loan', 'assigned_to').order_by('created'):
        loan = getattr(t, 'loan', None)
        rows.append((t.title, primary.get(t.pk, ''), loan.get_product_display() if loan else '',
                     loan.loanamount if loan else None, loan.loan_tenor if loan else None,
                     str(t.get_status_display()),
                     (t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else '',
                     t.created.astimezone(tz).replace(tzinfo=None),
                     t.due_date.astimezone(tz).replace(tzinfo=None) if t.due_date else None))
    ws = sheet(_('Application list'), [_('Application'), _('Primary applicant'), _('Product'), _('Loan amount'),
                                   _('Tenor'), _('Status'), _('With'), _('Created'), _('Due')], rows)
    for row in ws.iter_rows(min_row=2):
        row[3].number_format = '#,##0'
        row[7].number_format = row[8].number_format = 'dd/mm/yyyy hh:mm'

    sheet(_('Turnaround'), [_('Status'), _('Average days'), _('Steps counted')],
          [(row['status'], row['days'], row['count']) for row in data['turnaround']])
    sheet(_('Rejections'), [_('Reason'), _('Number of applications')],
          [(row['reason'], row['total']) for row in data['rejections']])
    month_rows = [(month, product, cell['count'], cell['amount'])
                  for month, by_product in data['monthly'].items() for product, cell in by_product.items()]
    ws = sheet(_('By month'), [_('Month'), _('Product'), _('Number of applications'), _('Amount (VND)')], month_rows)
    for row in ws.iter_rows(min_row=2):
        row[3].number_format = '#,##0'
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()
