"""
Who may see and edit a loan application.

``can_access_ticket`` / ``accessible_tickets``: which applications a user sees.
``editable_sections``: which part of an application a user may edit at its
current status. The admin (lwf/admin.py) and the workflow (lwf/workflow.py)
use these rules.
"""
from lwf.models import Ticket

# Groups that may open every application. 'SaleHead' and 'PFSHead' are the
# names the original code used; the database group is 'HeadPFS'.
ALL_TICKETS_GROUPS = ['SaleHead', 'PFSHead', 'HeadPFS', 'SaleAdmin']


def user_in_groups(user, *names):
    # The user's group names are read once per user object (one request), not per check.
    if not hasattr(user, '_lwf_group_names'):
        user._lwf_group_names = set(user.groups.values_list('name', flat=True)) if user.pk else set()
    return not user._lwf_group_names.isdisjoint(names)


def can_access_ticket(user, ticket):
    """True if the user may see and work on this application."""
    if user.is_superuser:
        return True
    role_holders = [ticket.submitter_id, ticket.ced_id, ticket.assigned_to_id,
                    ticket.slead_id, ticket.ssupport_id, ticket.sdirector_id, ticket.pfshead_id,
                    ticket.cra_id, ticket.approver1_id, ticket.approver2_id]
    if user.is_staff and user.pk in role_holders:
        return True
    if user_in_groups(user, *ALL_TICKETS_GROUPS):
        return True
    if ticket.ced_id and user_in_groups(user, 'CEDAdmin'):
        return True
    if ticket.cra_id and user_in_groups(user, 'CRAAdmin'):
        return True
    return False


# The groups each team admin manages.
TEAM_ADMIN_GROUPS = {
    'SaleAdmin': ['SaleHead', 'SaleManager', 'SaleSupport', 'SaleTeam', 'HeadPFS'],
    'CEDAdmin': ['CEDOfficer', 'Approver', 'ConcurApprover', 'ExceptionApprover', 'JDAApprover'],
    'CRAAdmin': ['CRAOfficer'],
}


def is_team_admin(user, ticket):
    """True if the user administers the team of the ticket's current handler."""
    if ticket.assigned_to is None:
        return False
    return any(user_in_groups(user, admin_group) and user_in_groups(ticket.assigned_to, *members)
               for admin_group, members in TEAM_ADMIN_GROUPS.items())


# Which part of an application each role may edit, and at which statuses.
SALE, CED, CRA = 'sale', 'ced', 'cra'
SALE_EDIT_STATUSES = (Ticket.OPEN_STATUS, Ticket.SS_RQ_UPDATE, Ticket.CED_RQ_UPDATE,
                      Ticket.CRA_RQ_UPDATE_STATUS, Ticket.CEDCK_RQ_UPDATE)
CED_EDIT_STATUSES = (Ticket.VERIFY_STATUS, Ticket.A1_RQ_UPDATE, Ticket.A2_RQ_UPDATE)
CRA_EDIT_STATUSES = (Ticket.DOCSPREP_STATUS, Ticket.DISBURSEMENT_STATUS)


def editable_sections(user, ticket):
    """
    The sections of this application the user may edit now: SALE (applicants,
    incomes, credit records, loan request, collateral), CED (credit decision,
    conditions, valuation) and CRA (contract data). Superusers may edit all.
    """
    if user.is_superuser:
        return {SALE, CED, CRA}
    sections = set()
    if ticket.status in SALE_EDIT_STATUSES and user.pk == ticket.submitter_id:
        sections.add(SALE)
    if ticket.status in CED_EDIT_STATUSES and (user.pk == ticket.ced_id or user_in_groups(user, 'CEDAdmin')):
        sections.add(CED)
    if ticket.status in CRA_EDIT_STATUSES and (user.pk == ticket.cra_id or user_in_groups(user, 'CRAAdmin')):
        sections.add(CRA)
    return sections


def field_section(name):
    """The section a field belongs to on models shared by several roles."""
    if name.startswith('cra_'):
        return CRA
    if name.startswith('ced_'):
        return CED
    return SALE


def accessible_tickets(user, queryset=None):
    """The applications can_access_ticket allows, as a queryset filter."""
    from django.db.models import Q
    queryset = Ticket.objects.all() if queryset is None else queryset
    if user.is_superuser or user_in_groups(user, *ALL_TICKETS_GROUPS):
        return queryset
    allowed = Q(pk__in=[])
    if user.is_staff:
        for role in ('submitter', 'ced', 'assigned_to', 'slead', 'ssupport', 'sdirector', 'pfshead',
                     'cra', 'approver1', 'approver2'):
            allowed |= Q(**{role: user})
    if user_in_groups(user, 'CEDAdmin'):
        allowed |= Q(ced__isnull=False)
    if user_in_groups(user, 'CRAAdmin'):
        allowed |= Q(cra__isnull=False)
    return queryset.filter(allowed)


# Sidebar permission callbacks (settings.UNFOLD); the admin classes enforce the same groups.
def is_superuser(request):
    return request.user.is_superuser


def can_manage_panels(request):
    return request.user.is_superuser or user_in_groups(request.user, 'CEDOfficer', 'CEDAdmin')


def can_manage_pricing(request):
    return request.user.is_superuser or user_in_groups(request.user, 'PFSAdmin')
