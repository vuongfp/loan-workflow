"""Reading applications and reference data; signing in from an app."""
import datetime
from typing import Optional

from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate
from ninja.throttling import AnonRateThrottle

from lwf import completeness, policy
from lwf.api import schemas
from lwf.api.auth import KEY_OR_TOKEN, TokenAuth, may_see_personal_data, require, visible_tickets
from lwf.models import (ApiClient, ApiToken, Applicant, CollaManager, CreditAssessment, CreditDecision, Disbursement,
                        FollowUp, LoanContract, Product, Ticket)

router = Router(tags=['applications'])
auth_router = Router(tags=['sign-in (apps)'])


def mask(id_number):
    value = id_number or ''
    return value[:3] + '*' * max(0, len(value) - 6) + value[-3:] if len(value) > 6 else '***'


def person(user):
    return (user.get_full_name() or user.username) if user else None


def summary(ticket):
    loan = getattr(ticket, 'loan', None)
    return {'number': ticket.title, 'status_code': ticket.status, 'status': str(ticket.get_status_display()),
            'handler': person(ticket.assigned_to), 'product': loan.get_product_display() if loan else None,
            'loan_amount': loan.loanamount if loan else None, 'tenor_months': loan.loan_tenor if loan else None,
            'created': ticket.created, 'modified': ticket.modified, 'due': ticket.due_date}


def get_ticket(request, number):
    return get_object_or_404(visible_tickets(request).select_related('loan', 'assigned_to'), title=number)


@router.get('/applications', response=list[schemas.ApplicationSummary], auth=KEY_OR_TOKEN,
            summary='List applications')
@paginate(LimitOffsetPagination)
def list_applications(request, status: Optional[int] = None, updated_since: Optional[datetime.datetime] = None):
    """Applications the caller may see, most recently changed first. Filter by status code or change time."""
    require(request, ApiClient.APPLICATIONS_READ)
    tickets = visible_tickets(request).select_related('loan', 'assigned_to').order_by('-modified')
    if status is not None:
        tickets = tickets.filter(status=status)
    if updated_since is not None:
        tickets = tickets.filter(modified__gte=updated_since)
    return [summary(ticket) for ticket in tickets]


@router.get('/applications/{number}', response=schemas.ApplicationDetail, auth=KEY_OR_TOKEN,
            summary='One application')
def application_detail(request, number: str):
    require(request, ApiClient.APPLICATIONS_READ)
    ticket = get_ticket(request, number)
    personal = may_see_personal_data(request)
    assessment = CreditAssessment.objects.filter(ticket=ticket).first()
    decision = CreditDecision.objects.filter(ticket=ticket).first()
    terms = LoanContract.objects.filter(ticket=ticket).first()
    return {
        **summary(ticket),
        'applicants': [{
            'name': applicant.name_vn, 'role': str(applicant.get_typeofapplicant_display()),
            'id_number': applicant.cid if personal else mask(applicant.cid),
            'date_of_birth': applicant.dob if personal else None, 'monthly_income': applicant.total or 0,
            'permanent_address': applicant.permanent_address_vn if personal else None,
        } for applicant in Applicant.objects.filter(ticket=ticket).order_by('typeofapplicant', 'pk')],
        'collaterals': [{'type': str(c.get_colla_type_display() or ''),
                         'value': c.spa_or_estimated or c.car_spa_value,
                         'address': c.fulladdress_vn if personal else None}
                        for c in CollaManager.objects.filter(ticket=ticket)],
        'assessment': assessment and {
            'monthly_income': assessment.monthly_income, 'existing_payments': assessment.exist_highest_installment,
            'dsr_highest': float(assessment.dsr_high or 0), 'net_surplus': assessment.nst,
            'segment': assessment.segmentation, 'crr_score': assessment.crr_score, 'crr_band': assessment.crr_band},
        'decision': decision and {'approved_amount': decision.approved_amount,
                                  'recommendation': decision.recommendation},
        'contract': contract_terms(terms),
        'missing_items': completeness.missing_items(ticket),
        'policy_breaches': [{'rule': b.rule, 'actual': b.actual, 'limit': b.limit, 'deviation_code': b.deviation}
                            for b in policy.breaches(ticket)],
    }


@router.get('/applications/{number}/history', response=list[schemas.HistoryEntry], auth=KEY_OR_TOKEN,
            summary='Workflow history of an application')
def application_history(request, number: str):
    require(request, ApiClient.APPLICATIONS_READ)
    ticket = get_ticket(request, number)
    return [{'date': step.date, 'by': person(step.user), 'step': step.title,
             'new_status': str(step.get_new_status_display()) if step.new_status else None, 'comment': step.comment}
            for step in FollowUp.objects.filter(ticket=ticket).select_related('user').order_by('date')]


def stage(ticket):
    return {Ticket.COMPLETE_STATUS: 'completed', Ticket.REJECT_STATUS: 'rejected',
            Ticket.CLOSED_STATUS: 'closed'}.get(ticket.status, 'in_progress')


def contract_terms(terms):
    return terms and {'loan_amount': terms.loan_amount, 'credit_limit': terms.credit_limit,
                      'disbursement_amount': terms.disbursement_amount, 'interest_rate': terms.interest_rate,
                      'margin': terms.margin, 'tenor_months': terms.tenor,
                      'disbursement_method': terms.disbursement_method}


@router.post('/customers/loans', response={200: schemas.CustomerLoans, 404: schemas.Problem}, auth=KEY_OR_TOKEN,
             tags=['customers'], summary="A customer's loans, by ID number")
def customer_loans(request, data: schemas.CustomerLookupIn):
    """Every application the customer is on (as borrower or co-borrower) that the caller may see, with the
    approved amount, contract terms and disbursements. The ID number is sent in the body, not the address,
    so that it does not end up in access logs."""
    require(request, ApiClient.APPLICATIONS_READ)
    personal = may_see_personal_data(request)
    on = (Applicant.objects.filter(cid=data.id_number.strip(), ticket__in=visible_tickets(request))
          .select_related('ticket', 'ticket__loan', 'ticket__assigned_to').order_by('-ticket__created', 'pk'))
    seen, rows = set(), []
    for applicant in on:
        if applicant.ticket_id not in seen:
            seen.add(applicant.ticket_id)
            rows.append(applicant)
    if not rows:
        return 404, {'detail': 'No loan application for this ID number.'}
    ticket_ids = [row.ticket_id for row in rows]
    decisions = {d.ticket_id: d for d in CreditDecision.objects.filter(ticket_id__in=ticket_ids)}
    contracts = {c.ticket_id: c for c in LoanContract.objects.filter(ticket_id__in=ticket_ids)}
    paid = {}
    for item in Disbursement.objects.filter(ticket_id__in=ticket_ids).order_by('disbursed_at'):
        paid.setdefault(item.ticket_id, []).append({
            'reference': item.reference, 'amount': item.amount, 'disbursed_at': item.disbursed_at,
            'account_number': item.account_number if personal else '****' + item.account_number[-4:]})
    loans = []
    for row in rows:
        ticket, decision = row.ticket, decisions.get(row.ticket_id)
        disbursements = paid.get(row.ticket_id, [])
        loans.append({**summary(ticket), 'stage': stage(ticket), 'role': str(row.get_typeofapplicant_display()),
                      'approved_amount': (decision.approved_amount or None) if decision else None,
                      'contract': contract_terms(contracts.get(row.ticket_id)),
                      'disbursed_amount': sum(item['amount'] for item in disbursements),
                      'disbursements': disbursements})
    latest = rows[0]
    return {'customer': {'name': latest.name_vn, 'id_number': latest.cid if personal else mask(latest.cid),
                         'date_of_birth': latest.dob if personal else None},
            'applications': len(loans),
            'in_progress': sum(loan['stage'] == 'in_progress' for loan in loans),
            'approved_total': sum(loan['approved_amount'] or 0 for loan in loans
                                  if loan['stage'] in ('in_progress', 'completed')),
            'disbursed_total': sum(loan['disbursed_amount'] for loan in loans),
            'loans': loans}


@router.get('/reference/products', response=list[schemas.Product], auth=KEY_OR_TOKEN, tags=['reference data'])
def products(request):
    require(request, ApiClient.REFERENCE_READ)
    return list(Product.objects.values('product_code', 'product', 'subproduct_code', 'subproduct'))


@router.get('/reference/statuses', response=list[schemas.Status], auth=KEY_OR_TOKEN, tags=['reference data'])
def statuses(request):
    require(request, ApiClient.REFERENCE_READ)
    return [{'code': code, 'name': str(name)} for code, name in Ticket.STATUS_CHOICES]


# ------------------------------------------------------------ sign-in for apps

@auth_router.post('/token', response={200: schemas.TokenOut, 401: schemas.Problem}, auth=None,
                  throttle=[AnonRateThrottle('10/m')], summary='Sign in and get a token')
def sign_in(request, data: schemas.TokenIn):
    """For the mobile app: a token valid for 12 hours, sent as `Authorization: Bearer <token>`."""
    user = authenticate(request, username=data.username, password=data.password)
    if user is None or not user.is_staff:
        return 401, {'detail': 'Wrong username or password.'}
    token, raw = ApiToken.issue(user, data.device)
    return {'token': raw, 'expires': token.expires}


@auth_router.post('/logout', response={204: None}, auth=TokenAuth(), summary='Sign out (end the token)')
def sign_out(request):
    request.auth.delete()
    return 204, None


@auth_router.get('/me', response=schemas.MeOut, auth=TokenAuth(), summary='Who the token belongs to')
def me(request):
    user = request.auth.user
    if not user.is_active:
        raise HttpError(401, 'Inactive user.')
    return {'username': user.username, 'full_name': user.get_full_name(),
            'groups': list(user.groups.values_list('name', flat=True))}
