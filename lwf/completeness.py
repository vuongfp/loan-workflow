"""
Is an application complete enough for Sale to send it on? The checks are a
demo assumption of what the bank requires; Sale cannot move the application
forward from a Sale step until every check passes.
"""
from dataclasses import dataclass

from django.utils.translation import gettext as _

from lwf.models import LOV, Applicant, AttachDocument, CollaManager, CreditAssessment, LoanDetail

# Document groups (AttachDocument.related_data) every application needs.
REQUIRED_DOCUMENT_GROUPS = (1, 2, 3, 4)


@dataclass
class Check:
    label: str
    ok: bool


def checks(ticket):
    """Every check, passed or not, in the order Sale fills the application."""
    primary = Applicant.objects.filter(ticket=ticket, typeofapplicant=1).first()
    loan = LoanDetail.objects.filter(ticket=ticket).first()
    assessment = CreditAssessment.objects.filter(ticket=ticket).first()
    collaterals = list(CollaManager.objects.filter(ticket=ticket))
    groups = set(AttachDocument.objects.filter(ticket=ticket).values_list('related_data', flat=True))
    deviations_explained = bool(loan) and all(
        details for chosen, details in ((loan.deviation1, loan.deviation1_details),
                                        (loan.deviation2, loan.deviation2_details)) if chosen)
    result = [
        Check(_('Primary applicant with name, ID number and date of birth'),
              bool(primary and primary.name_vn and primary.cid and primary.dob)),
        Check(_('Monthly income entered'), bool(assessment and (assessment.monthly_income or 0) > 0)),
        Check(_('Loan request: product, amount, tenor and pricing scheme'),
              bool(loan and loan.product and loan.loanamount and loan.loan_tenor and loan.loan_pricing_scheme_id)),
        Check(_('At least one collateral with its value'),
              any((c.spa_or_estimated or c.car_spa_value or 0) > 0 for c in collaterals)),
        Check(_('A reason for each deviation chosen'), deviations_explained),
    ]
    labels = dict(LOV.RELATED_DATA_CHOICES)
    result += [Check(_('Document: %s') % labels[group], group in groups) for group in REQUIRED_DOCUMENT_GROUPS]
    return result


def missing_items(ticket):
    return [check.label for check in checks(ticket) if not check.ok]
