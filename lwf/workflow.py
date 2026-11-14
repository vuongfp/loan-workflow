"""
Loan application workflow: the steps a user can take now and taking them.

The steps come from the Action table (status + approval type + acting group
-> next status + next group), so the business can change the workflow in the
admin. Every status change goes through transition(), which re-checks the
rules on the locked row, fills the role fields, writes the history and
notifies the new handler.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from lwf import completeness, notifications
from lwf.access import SALE_EDIT_STATUSES, can_access_ticket, is_team_admin, user_in_groups
from lwf.models import LOV, Action, FollowUp, LoanDetail, Notification, Officer, Ticket, TicketChange

User = get_user_model()

# Next statuses that send the application back to the person who submitted it.
RETURN_TO_SUBMITTER = {Ticket.REJECT_STATUS, Ticket.OPEN_STATUS, Ticket.CLOSED_STATUS, Ticket.SS_RQ_UPDATE,
                       Ticket.POST_APPROVAL, Ticket.CRA_RQ_UPDATE_STATUS, Ticket.CEDCK_RQ_UPDATE,
                       Ticket.CED_RQ_UPDATE}
# The role field filled the first time an application reaches a status.
ROLE_FIELD_BY_STATUS = {
    Ticket.ENDORSE_STATUS: 'slead', Ticket.SUPPORT_STATUS: 'ssupport',
    Ticket.SD_APPROVE_EXCEPTION: 'sdirector', Ticket.HS_APPROVE_EXCEPTION: 'pfshead',
    Ticket.VERIFY_STATUS: 'ced', Ticket.APPROVER1_STATUS: 'approver1', Ticket.APPROVER2_STATUS: 'approver2',
    Ticket.DOCSPREP_STATUS: 'cra',
}
FINISHED_STATUSES = (Ticket.CLOSED_STATUS, Ticket.COMPLETE_STATUS, Ticket.REJECT_STATUS)
# Each handler has this long for their step (demo assumption: calendar days).
STEP_DAYS = 3
CREDIT_GROUPS = ('CEDOfficer', 'Approver', 'ConcurApprover', 'ExceptionApprover', 'JDAApprover')


def available_actions(user, ticket):
    """The Action rows this user may take on the application now."""
    if not can_access_ticket(user, ticket):
        return []
    # Four-eyes rule: the first approver does not also give the second approval.
    if ticket.status == Ticket.APPROVER2_STATUS and user.pk == ticket.approver1_id:
        return []
    actions = Action.objects.filter(status=ticket.status).select_related('team', 'next_team').order_by('id')
    if not user.is_superuser:
        actions = actions.filter(team__in=user.groups.all())
    for apprtype in (ticket.apprtype, 3):     # the approval path, else the normal path
        found = list(actions.filter(apprtype=apprtype))
        if found:
            return found
    return []


def round_robin_officer(team_name):
    """The available officer of a team with the fewest open applications assigned."""
    officer = (Officer.objects.filter(mainteam__name=team_name, available=True)
               .annotate(open_count=Count('user__assigned_to', filter=~Q(
                   user__assigned_to__status__in=FINISHED_STATUSES)))
               .order_by('open_count', 'user_id').select_related('user').first())
    return officer.user if officer else None


@dataclass
class AssigneeChoice:
    users: list
    suggested: object   # a User or None


def assignee_choices(action, ticket, user):
    """Who can receive the application after `action`, and who to suggest."""
    next_status = action.next_status
    team = list(User.objects.filter(groups=action.next_team, is_active=True).order_by('username'))
    if next_status in RETURN_TO_SUBMITTER and ticket.submitter:
        return AssigneeChoice([ticket.submitter], ticket.submitter)
    if next_status == Ticket.SUPPORT_STATUS and ticket.ssupport:
        return AssigneeChoice([ticket.ssupport], ticket.ssupport)
    if next_status in (Ticket.VALUATION_STATUS, Ticket.A1_RQ_UPDATE, Ticket.A2_RQ_UPDATE) and ticket.ced:
        return AssigneeChoice([ticket.ced], ticket.ced)
    if next_status == Ticket.APPROVER2_STATUS:
        team = [u for u in team if u.pk not in (user.pk, ticket.approver1_id)]
    for status, role, group in ((Ticket.VERIFY_STATUS, 'ced', 'CEDOfficer'),
                                (Ticket.DOCSPREP_STATUS, 'cra', 'CRAOfficer')):
        if next_status == status:
            holder = getattr(ticket, role)
            if holder:
                return AssigneeChoice([holder], holder)
            suggested = round_robin_officer(group)
            if suggested and suggested not in team:
                team.insert(0, suggested)
            return AssigneeChoice(team, suggested)
    if ticket.submitter in team:
        # Back to the Sale team: the officer who submitted the application.
        return AssigneeChoice(team, ticket.submitter)
    return AssigneeChoice(team, team[0] if len(team) == 1 else None)


# How a step moves the application: on, back for changes, or out of the workflow.
STEP_KINDS = ('forward', 'back', 'stop')
SEND_BACK_STATUSES = {Ticket.SS_RQ_UPDATE, Ticket.CED_RQ_UPDATE, Ticket.A1_RQ_UPDATE, Ticket.A2_RQ_UPDATE,
                      Ticket.CRA_RQ_UPDATE_STATUS, Ticket.CEDCK_RQ_UPDATE}


def step_kind(action):
    if action.next_status in (Ticket.REJECT_STATUS, Ticket.CLOSED_STATUS):
        return 'stop'
    if action.next_status in SEND_BACK_STATUSES or (action.next_status == Ticket.OPEN_STATUS
                                                     and action.status != Ticket.REJECT_STATUS):
        return 'back'
    return 'forward'


def needs_complete_application(action, ticket):
    """Sale sends the application on from one of its own steps."""
    return ticket.status in SALE_EDIT_STATUSES and step_kind(action) == 'forward'


def needs_reject_code(action, user):
    return action.next_status == Ticket.REJECT_STATUS and user_in_groups(user, *CREDIT_GROUPS)


def needs_qc_code(action, user):
    return (action.next_status in (Ticket.CED_RQ_UPDATE, Ticket.CEDCK_RQ_UPDATE)
            and user_in_groups(user, 'CEDOfficer'))


def disbursement_number(ticket):
    """DS.<AL|PSL|SS>.<yy>.<nnnn>: the number an application gets when it reaches CED."""
    loan = LoanDetail.objects.filter(ticket=ticket).first()
    product = {6: 'AL', 3: 'PSL'}.get(loan.product if loan else None, 'SS')
    prefix = 'DS.%s.%s.' % (product, timezone.now().strftime('%y'))
    sequence = Ticket.objects.filter(title__startswith=prefix).count() + 1
    while Ticket.objects.filter(title='%s%04d' % (prefix, sequence)).exists():
        sequence += 1
    return '%s%04d' % (prefix, sequence)


def _history(ticket, user, title, comment, new_status=None, changes=()):
    followup = FollowUp.objects.create(ticket=ticket, date=timezone.now(), title=title, comment=comment,
                                       user=user, new_status=new_status)
    TicketChange.objects.bulk_create([TicketChange(followup=followup, field=field, old_value=old, new_value=new)
                                      for field, old, new in changes if str(old) != str(new)])
    return followup


def _notify(ticket, assignee):
    if assignee and assignee.email:
        from lwf.tasks import notify_assignee
        transaction.on_commit(lambda: notify_assignee.enqueue(ticket.pk, assignee.pk))


def _person(user):
    return user.get_full_name() or user.get_username() if user else ''


@transaction.atomic
def transition(ticket, action, user, assignee, comment='', reject_code=None, qc_code=None):
    """
    Take `action` on the application and hand it to `assignee`. Raises
    PermissionDenied if the user may not take the action now, ValidationError
    if the assignee or codes are not acceptable.
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if action.pk not in {a.pk for a in available_actions(user, ticket)}:
        raise PermissionDenied(_('This step is not available to you at the current status.'))
    if needs_complete_application(action, ticket):
        missing = completeness.missing_items(ticket)
        if missing:
            raise ValidationError(_('Complete the application first: %s.') % '; '.join(missing))
    choices = assignee_choices(action, ticket, user)
    if assignee not in choices.users:
        raise ValidationError(_('Choose who receives the application from the list.'))
    if needs_reject_code(action, user):
        if reject_code not in dict(LOV.REJECT_CHOICES):
            raise ValidationError(_('Choose a rejection reason.'))
        ticket.reject_code = reject_code
    if qc_code is not None and needs_qc_code(action, user):
        comment = '%s: %s\n%s' % (_('QC'), dict(LOV.QC_CHOICES).get(qc_code, qc_code), comment)

    old = {'status': ticket.get_status_display(), 'owner': _person(ticket.assigned_to), 'title': ticket.title}
    ticket.status = action.next_status
    ticket.assigned_to = assignee
    finished = action.next_status in FINISHED_STATUSES
    ticket.due_date = None if finished else timezone.now() + timedelta(days=STEP_DAYS)
    role = ROLE_FIELD_BY_STATUS.get(action.next_status)
    if role and getattr(ticket, role) is None:
        setattr(ticket, role, assignee)
    if action.next_status == Ticket.VERIFY_STATUS and not ticket.title.startswith('DS.'):
        ticket.title = disbursement_number(ticket)
        ticket.submitted = timezone.now()
    ticket.save()

    _history(ticket, user, action.description or ticket.get_status_display(), comment, action.next_status, [
        (_('Status'), old['status'], ticket.get_status_display()),
        (_('Owner'), old['owner'], _person(assignee)),
        (_('Title'), old['title'], ticket.title),
    ])
    kinds = {'back': Notification.SENT_BACK, 'stop': Notification.CLOSED}
    kind = kinds.get(step_kind(action), Notification.ASSIGNED)
    notifications.notify(assignee, ticket, kind, actor=user, status=action.next_status)
    _notify(ticket, assignee)
    return ticket


def reassign_choices(ticket):
    """Users of the group handling the current status."""
    teams = Action.objects.filter(status=ticket.status).values('team')
    return list(User.objects.filter(groups__in=teams, is_active=True).distinct().order_by('username'))


@transaction.atomic
def reassign(ticket, user, assignee, comment=''):
    """Hand the application to another member of the same team; the status does not change."""
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not (user.is_superuser or is_team_admin(user, ticket)):
        raise PermissionDenied(_('Only the team admin can re-assign this application.'))
    if assignee not in reassign_choices(ticket):
        raise ValidationError(_('Choose a member of the team handling this step.'))
    old_owner = _person(ticket.assigned_to)
    for role in ('ced', 'cra'):
        if getattr(ticket, role + '_id') == ticket.assigned_to_id and ticket.assigned_to_id:
            setattr(ticket, role, assignee)
    ticket.assigned_to = assignee
    ticket.save(update_fields=['assigned_to', 'ced', 'cra', 'modified'])
    _history(ticket, user, _('Re-assigned'), comment, None, [(_('Owner'), old_owner, _person(assignee))])
    notifications.notify(assignee, ticket, Notification.REASSIGNED, actor=user, status=ticket.status)
    _notify(ticket, assignee)
    return ticket
