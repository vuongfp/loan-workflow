"""Core banking, credit bureau (CIC) and eKYC: other systems sending data in."""
from django.shortcuts import get_object_or_404
from ninja import Router

from lwf import integrations
from lwf.api import schemas
from lwf.api.applications import person
from lwf.api.auth import KEY_OR_TOKEN, KeyAuth, caller_name, require, visible_tickets
from lwf.models import ApiClient, Applicant, Disbursement, Ticket

router = Router()


@router.get('/core-banking/ready', response=list[schemas.ReadyForDisbursement], auth=KeyAuth(),
            tags=['core banking'], summary='Applications waiting for disbursement')
def ready(request):
    require(request, ApiClient.CORE_BANKING)
    result = []
    for ticket in integrations.ready_for_disbursement():
        borrower = Applicant.objects.filter(ticket=ticket, typeofapplicant=1).first()
        terms = getattr(ticket, 'contract', None)
        result.append({
            'number': ticket.title, 'borrower': borrower.name_vn if borrower else None,
            'borrower_id_number': borrower.cid if borrower else None,
            'disbursement_amount': terms.disbursement_amount if terms else None,
            'already_disbursed': sum(Disbursement.objects.filter(ticket=ticket).values_list('amount', flat=True)),
            'interest_rate': terms.interest_rate if terms else None, 'tenor_months': terms.tenor if terms else None,
            'disbursement_method': terms.disbursement_method if terms else None, 'cra_officer': person(ticket.cra),
        })
    return result


@router.post('/core-banking/disbursements', response={200: schemas.DisbursementOut, 201: schemas.DisbursementOut,
                                                       404: schemas.Problem, 409: schemas.Problem,
                                                       422: schemas.Problem},
             auth=KeyAuth(), tags=['core banking'], summary='Report a disbursement')
def disbursement(request, data: schemas.DisbursementIn):
    """Records the disbursement and tells the CRA officer, who confirms the step. Safe to repeat."""
    require(request, ApiClient.CORE_BANKING)
    ticket = get_object_or_404(Ticket, title=data.application)
    try:
        record, created = integrations.record_disbursement(ticket, data.reference, data.amount, data.disbursed_at,
                                                           data.account_number, client=request.auth)
    except integrations.IntegrationError as error:
        return error.status, {'detail': str(error)}
    return (201 if created else 200), {
        'application': ticket.title, 'reference': record.reference, 'amount': record.amount,
        'disbursed_at': record.disbursed_at, 'account_number': record.account_number, 'created': created}


@router.post('/cic/reports', response={200: schemas.CicReportOut, 404: schemas.Problem}, auth=KeyAuth(),
             tags=['credit bureau'], summary='Send a credit bureau report')
def cic_report(request, data: schemas.CicReportIn):
    """Replaces the CIC records of every applicant with this ID number on applications in progress."""
    require(request, ApiClient.CIC)
    applicants = integrations.open_applicants(data.id_number)
    if not applicants:
        return 404, {'detail': 'No application in progress has an applicant with this ID number.'}
    for applicant in applicants:
        integrations.apply_cic_report(applicant, data.dict(), source=caller_name(request))
    return {'applications_updated': sorted({applicant.ticket.title for applicant in applicants})}


@router.post('/ekyc/checks', response={201: schemas.EkycOut, 404: schemas.Problem}, auth=KEY_OR_TOKEN,
             tags=['eKYC'], summary='Send an eKYC result (chip ID card and face match)')
def ekyc_check(request, data: schemas.EkycIn):
    """From an eKYC system, or from the Sale officer's app after reading the customer's chip ID card."""
    require(request, ApiClient.EKYC)
    ticket = get_object_or_404(visible_tickets(request), title=data.application)
    try:
        check = integrations.record_ekyc(ticket, data.dict(), source=caller_name(request))
    except integrations.IntegrationError as error:
        return error.status, {'detail': str(error)}
    return 201, {'passed': check.passed, 'differences': check.mismatches, 'applicant': check.applicant.name_vn}
