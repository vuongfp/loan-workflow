"""
What other systems send in, used by the API and the admin alike: disbursements
from core banking, credit bureau (CIC) reports, eKYC results.
"""
import datetime
import random
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from lwf import notifications, services
from lwf.calculations import ascii_upper
from lwf.models import (Applicant, CicCreditCard, CicOverDraft, CicReport, CicSecureLoan, CicUnSecureLoan,
                        Disbursement, EkycCheck, FollowUp, LoanContract, LoanDetail, Notification, Ticket)
from lwf.workflow import FINISHED_STATUSES

# eKYC passes from this face match score (0-100); a demo assumption.
FACE_MATCH_MIN = 80
CREDIT_GROUPS = ('NoCIC', 'G1', 'G2', 'G3', 'G4', 'G5')


class IntegrationError(Exception):
    """The request cannot be applied; `status` is the HTTP status the API answers with."""

    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------ core banking

def ready_for_disbursement():
    return (Ticket.objects.filter(status=Ticket.DISBURSEMENT_STATUS)
            .select_related('loan', 'contract', 'cra').order_by('modified'))


@transaction.atomic
def record_disbursement(ticket, reference, amount, disbursed_at, account_number, client=None):
    """
    Record a disbursement core banking made. The same reference again returns the
    first record (created=False), so a retried call does no harm. The CRA
    handler is told; CRA then confirms the step in the workflow.
    """
    existing = Disbursement.objects.filter(reference=reference).first()
    if existing:
        if existing.ticket_id != ticket.pk:
            raise IntegrationError(_('This reference was already used for another application.'), 409)
        return existing, False
    if ticket.status != Ticket.DISBURSEMENT_STATUS:
        raise IntegrationError(_('The application is not waiting for disbursement.'), 409)
    terms = LoanContract.objects.filter(ticket=ticket).first()
    limit = (terms and terms.disbursement_amount) or LoanDetail.objects.get(ticket=ticket).loanamount or 0
    already = sum(Disbursement.objects.filter(ticket=ticket).values_list('amount', flat=True))
    if amount <= 0 or already + amount > limit:
        raise IntegrationError(_('The amount is more than the contract allows (%(limit)s VND, %(done)s VND '
                                 'disbursed already).') % {'limit': '{:,}'.format(limit),
                                                           'done': '{:,}'.format(already)})
    disbursement = Disbursement.objects.create(ticket=ticket, reference=reference, amount=amount,
                                               disbursed_at=disbursed_at, account_number=account_number,
                                               client=client)
    FollowUp.objects.create(ticket=ticket, date=timezone.now(), title=_('Core banking disbursement'),
                            comment=_('%(amount)s VND to loan account %(account)s, reference %(reference)s.') % {
                                'amount': '{:,}'.format(amount), 'account': account_number, 'reference': reference})
    notifications.notify(ticket.cra or ticket.assigned_to, ticket, Notification.DISBURSED)
    return disbursement, True


# ------------------------------------------------------------ credit bureau (CIC)

@dataclass
class CicLoans:
    secured: list
    unsecured: list
    overdrafts: list
    credit_cards: list


def open_applicants(id_number):
    """The applicants with this ID number on applications still in progress."""
    return list(Applicant.objects.filter(cid=id_number).exclude(ticket__status__in=FINISHED_STATUSES)
                .select_related('ticket'))


@transaction.atomic
def apply_cic_report(applicant, report, source):
    """
    Replace the applicant's CIC records with the report's and recalculate the
    application. `report` is the API's CIC report (dict).
    """
    applicant.cic_reports.create(report_date=report['report_date'], source=source,
                                 credit_group=report.get('credit_group') or '',
                                 data={**report, 'report_date': str(report['report_date'])})
    for model in (CicSecureLoan, CicUnSecureLoan, CicOverDraft, CicCreditCard):
        model.objects.filter(applicant=applicant).delete()
    for loan in report.get('secured_loans', []):
        CicSecureLoan.objects.create(applicant=applicant, original_amount=loan['original_amount'],
                                     interest_rate=loan['interest_rate'], loan_tenor=loan['tenor_months'],
                                     outstanding_loan=loan['outstanding'],
                                     progressive_disbursement=loan.get('progressive_disbursement', False))
    for loan in report.get('unsecured_loans', []):
        payments = (list(loan['monthly_payments']) + [0, 0, 0])[:3]
        CicUnSecureLoan.objects.create(applicant=applicant, m1=payments[0], m2=payments[1], m3=payments[2])
    for loan in report.get('overdrafts', []):
        CicOverDraft.objects.create(applicant=applicant, interest_rate=loan['interest_rate'],
                                    outstanding_loan=loan['outstanding'])
    for card in report.get('credit_cards', []):
        balances = (list(card['balances']) + [0] * 6)[:6]
        CicCreditCard.objects.create(applicant=applicant, **{'bm%d' % i: balances[i - 1] for i in range(1, 7)})
    applicant.cicdate = report['report_date']
    if report.get('credit_group') in CREDIT_GROUPS:
        applicant.cic5Y = report['credit_group']
    applicant.total_outstanding = (sum(loan['outstanding'] for loan in report.get('secured_loans', []))
                                   + sum(loan['outstanding'] for loan in report.get('overdrafts', [])))
    applicant.save(update_fields=['cicdate', 'cic5Y', 'total_outstanding'])
    services.recalc_credit_summary(applicant.ticket)
    return applicant


def demo_cic_report(id_number):
    """A made-up but stable bureau report for an ID number: the demo stands in for the CIC connection."""
    rng = random.Random('cic-%s' % id_number)
    report = {'id_number': id_number, 'report_date': timezone.localdate(),
              'credit_group': rng.choice(('NoCIC', 'G1', 'G1', 'G1', 'G2')),
              'secured_loans': [], 'unsecured_loans': [], 'overdrafts': [], 'credit_cards': []}
    if report['credit_group'] == 'NoCIC':
        return report
    amount = rng.randrange(2, 8) * 100_000_000
    report['secured_loans'].append({'original_amount': amount, 'interest_rate': rng.choice((9.5, 10.5, 11.0)),
                                    'tenor_months': rng.choice((120, 180, 240)),
                                    'outstanding': amount * rng.randint(30, 90) // 100})
    if rng.random() < 0.6:
        report['credit_cards'].append({'balances': [rng.randrange(2, 40) * 1_000_000 for _ in range(6)]})
    if rng.random() < 0.3:
        report['unsecured_loans'].append({'monthly_payments': [3_000_000] * 3})
    return report


# ------------------------------------------------------------ eKYC

def _same_name(left, right):
    return ascii_upper(left or '').split() == ascii_upper(right or '').split()


@transaction.atomic
def record_ekyc(ticket, data, source):
    """
    Compare what the chip ID card and the face check returned with the applicant
    on the application. Empty contract fields (ID issue date and place,
    permanent address) are filled from the chip, which is the official source.
    """
    applicant = Applicant.objects.filter(ticket=ticket, cid=data['id_number']).first()
    if applicant is None:
        raise IntegrationError(_('No applicant with this ID number on the application.'), 404)
    mismatches = []
    if not _same_name(applicant.name_vn, data['full_name']):
        mismatches.append('full_name')
    if applicant.dob and data.get('date_of_birth') and applicant.dob != data['date_of_birth']:
        mismatches.append('date_of_birth')
    score = data.get('face_match_score')
    passed = bool(data.get('chip_verified')) and not mismatches and score is not None and score >= FACE_MATCH_MIN
    changed = []
    for field, key in (('cra_id_date', 'issue_date'), ('cra_id_place', 'issue_place'),
                       ('cra_permanent_address', 'permanent_address')):
        if data.get(key) and not getattr(applicant, field):
            setattr(applicant, field, data[key])
            changed.append(field)
    if changed:
        applicant.save(update_fields=changed)
    stored = {key: (value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) else value)
              for key, value in data.items()}
    return EkycCheck.objects.create(applicant=applicant, data=stored, chip_verified=bool(data.get('chip_verified')),
                                    face_match_score=score, passed=passed, mismatches=mismatches, source=source)
