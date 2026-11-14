"""
Automatic credit policy checks: the limits of the application's product
(CreditPolicy) against its loan request, applicants and repayment capacity.
A breach is not blocking; it says which deviation code to declare.
"""
from dataclasses import dataclass

from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.translation import gettext as _

from lwf.models import LOV, Applicant, CreditAssessment, CreditPolicy, LoanDetail

# Deviation codes of LOV.DEVIATION_CHOICES.
TENOR, MOA, AGE, REPAYMENT, AMOUNT = 101, 102, 104, 107, 110


@dataclass
class Breach:
    rule: str
    actual: str
    limit: str
    deviation: int

    @property
    def deviation_label(self):
        return dict(LOV.DEVIATION_CHOICES).get(self.deviation, self.deviation)


def breaches(ticket):
    loan = LoanDetail.objects.filter(ticket=ticket).first()
    if not loan:
        return []
    policy = CreditPolicy.for_product(loan.product)
    if not policy:
        return []
    assessment = CreditAssessment.objects.filter(ticket=ticket).first()
    primary = Applicant.objects.filter(ticket=ticket, typeofapplicant=1).first()
    found = []

    def check(rule, actual, limit, too_high, deviation, show=str):
        if actual is None or limit is None:
            return
        if (actual > limit) if too_high else (actual < limit):
            found.append(Breach(rule, show(actual), show(limit), deviation))

    money = lambda value: '%s VND' % intcomma(value)
    percent = lambda value: '%s%%' % value
    check(_('Tenor'), loan.loan_tenor or None, policy.max_tenor, True, TENOR, lambda v: _('%s months') % v)
    check(_('Loan to value'), loan.loan_moa or None, policy.max_ltv, True, MOA, percent)
    check(_('Loan amount'), loan.loanamount or None, policy.max_loan_amount, True, AMOUNT, money)
    if primary and primary.age is not None and loan.loan_tenor:
        age_at_maturity = primary.age + -(-loan.loan_tenor // 12)
        check(_('Age at maturity'), age_at_maturity, policy.max_age_at_maturity, True, AGE,
              lambda v: _('%s years') % v)
    if assessment:
        check(_('DSR'), assessment.dsr_high, policy.max_dsr, True, REPAYMENT, percent)
        check(_('Monthly income'), assessment.monthly_income or None, policy.min_monthly_income, False, REPAYMENT,
              money)
        check(_('Net surplus after payments'), assessment.nst, policy.min_net_surplus, False, REPAYMENT, money)
    return found


def suggested_deviations(ticket):
    """Deviation codes the breaches call for that the loan request does not declare yet."""
    loan = LoanDetail.objects.filter(ticket=ticket).first()
    declared = {loan.deviation1, loan.deviation2} if loan else set()
    return sorted({breach.deviation for breach in breaches(ticket)} - declared)
