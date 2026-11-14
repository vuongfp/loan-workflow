"""
Credit calculations for a loan application.

All amounts are whole VND (integers); ratios use Decimal. The functions read
what they need with a fixed number of queries per application, whatever the
number of applicants or income records.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from lwf.models import (Applicant, BusinessIncome, CicCreditCard, CicOverDraft, CicSecureLoan,
                        CicUnSecureLoan, CreditSettings, HouseholdIncome, LoanDetail, RentalIncome,
                        SalaryIncome, CreditAssessment)

SAL, RTL, SHH, SEC = 'Salary earner-SAL', 'Rental-RTL', 'Self-employed(Household Biz)-SHH', 'Self-employed-SEC'
EMPLOYMENT_SELF, EMPLOYMENT_SALARY, EMPLOYMENT_RENTAL = 1, 2, 3


def whole_vnd(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def loan_installments(amount, tenor_months, annual_rate_percent):
    """
    Monthly payments of a loan repaid in equal principal parts with interest on
    the remaining balance: (highest, lowest, average). The first month is the
    highest (full balance), the last the lowest (one principal part left).
    """
    if not amount or not tenor_months:
        return 0, 0, 0
    principal_part = Decimal(amount) / Decimal(tenor_months)
    monthly_rate = Decimal(annual_rate_percent or 0) / Decimal(1200)
    highest = principal_part + Decimal(amount) * monthly_rate
    lowest = principal_part * (1 + monthly_rate)
    return whole_vnd(highest), whole_vnd(lowest), whole_vnd((highest + lowest) / 2)


def update_loan_installments(loan):
    rate = loan.loan_pricing_scheme.normal if loan.loan_pricing_scheme_id else 0
    loan.highest_installment, loan.lowest_installment, loan.average_installment = \
        loan_installments(loan.loanamount, loan.loan_tenor, rate)
    loan.save(update_fields=['highest_installment', 'lowest_installment', 'average_installment'])


def _sums_by_applicant(model, ticket, *fields):
    """{applicant_id: {field: sum}} for one income or credit table, in one query."""
    rows = (model.objects.filter(applicant__ticket=ticket).values('applicant')
            .annotate(**{field: Sum(field) for field in fields}))
    return {row['applicant']: {field: row[field] or 0 for field in fields} for row in rows}


def segmentation(salary, business, household, rental, settings):
    """Customer segment and employment type from monthly incomes (VND)."""
    total = salary + business + household + rental
    if salary > total * settings.salary_segment_min_share and salary > settings.salary_segment_min_income:
        return SAL, EMPLOYMENT_SALARY
    if rental > max(business, salary, household):
        return RTL, EMPLOYMENT_RENTAL
    if household > business:
        return SHH, EMPLOYMENT_SELF
    return SEC, EMPLOYMENT_SELF


def tat_segmentation(business, household, rental):
    if rental > 0 or household > 0:
        return 'RTL/SHH'
    return 'SEC' if business > 0 else 'SAL'


def length_in_service_months(primary, segment):
    """Months in the current job or business of the primary applicant (0 if unknown)."""
    if primary is None:
        return 0
    if segment == SAL:
        job = SalaryIncome.objects.filter(applicant=primary).order_by('-avg').first()
        return (job.length_in_service or 0) if job else 0
    if segment == RTL:
        return 0
    model = HouseholdIncome if segment == SHH else BusinessIncome
    business = model.objects.filter(applicant=primary).order_by('-netincome').first()
    return (business.years or 0) * 12 if business else 0


def recalc_income(ticket, settings=None):
    """Monthly incomes per applicant and for the application, plus segmentation."""
    settings = settings or CreditSettings.load()
    applicants = list(Applicant.objects.filter(ticket=ticket))
    salary = _sums_by_applicant(SalaryIncome, ticket, 'fix_avg', 'var_avg')
    business = _sums_by_applicant(BusinessIncome, ticket, 'netincome')
    household = _sums_by_applicant(HouseholdIncome, ticket, 'netincome')
    rental = _sums_by_applicant(RentalIncome, ticket, 'net_income')
    for applicant in applicants:
        applicant.fix = salary.get(applicant.pk, {}).get('fix_avg', 0)
        applicant.var = salary.get(applicant.pk, {}).get('var_avg', 0)
        applicant.net = applicant.fix + applicant.var
        applicant.business = business.get(applicant.pk, {}).get('netincome', 0)
        applicant.household = household.get(applicant.pk, {}).get('netincome', 0)
        applicant.rental = rental.get(applicant.pk, {}).get('net_income', 0)
        applicant.total = applicant.net + applicant.business + applicant.household + applicant.rental
    Applicant.objects.bulk_update(applicants, ['fix', 'var', 'net', 'business', 'household', 'rental', 'total'])

    detail, _created = CreditAssessment.objects.get_or_create(ticket=ticket)
    detail.net_income = sum(a.net for a in applicants)
    detail.biz_income = sum(a.business for a in applicants)
    detail.hhold_income = sum(a.household for a in applicants)
    detail.rental_income = sum(a.rental for a in applicants)
    detail.crr_biz_income = detail.biz_income + detail.hhold_income
    detail.monthly_income = sum(a.total for a in applicants)
    detail.segmentation, detail.employment_type = segmentation(
        detail.net_income, detail.biz_income, detail.hhold_income, detail.rental_income, settings)
    primary = next((a for a in applicants if a.typeofapplicant == 1), None)
    detail.lengthinservice = length_in_service_months(primary, detail.segmentation)
    detail.tatsegmentation = tat_segmentation(detail.biz_income, detail.hhold_income, detail.rental_income)
    detail.save()
    return detail


def recalc_existing_installments(ticket):
    """Monthly payments on the applicants' existing debts (from CIC records)."""
    secured = _sums_by_applicant(CicSecureLoan, ticket, 'highest_installment', 'averageinstallment')
    unsecured = _sums_by_applicant(CicUnSecureLoan, ticket, 'installment')
    overdraft = _sums_by_applicant(CicOverDraft, ticket, 'installment')
    cards = _sums_by_applicant(CicCreditCard, ticket, 'highest_installment', 'averageinstallment')
    applicants = list(Applicant.objects.filter(ticket=ticket))
    for applicant in applicants:
        fixed = (unsecured.get(applicant.pk, {}).get('installment', 0)
                 + overdraft.get(applicant.pk, {}).get('installment', 0))
        applicant.highest_installment = (secured.get(applicant.pk, {}).get('highest_installment', 0)
                                        + cards.get(applicant.pk, {}).get('highest_installment', 0) + fixed)
        applicant.average_installment = (secured.get(applicant.pk, {}).get('averageinstallment', 0)
                                        + cards.get(applicant.pk, {}).get('averageinstallment', 0) + fixed)
    Applicant.objects.bulk_update(applicants, ['highest_installment', 'average_installment'])

    detail, _created = CreditAssessment.objects.get_or_create(ticket=ticket)
    detail.exist_highest_installment = sum(a.highest_installment for a in applicants)
    detail.exist_average_installment = sum(a.average_installment for a in applicants)
    detail.save(update_fields=['exist_highest_installment', 'exist_average_installment'])
    return detail


def default_expenditure(ticket, settings=None):
    """Default monthly living cost: the primary applicant plus each other applicant."""
    settings = settings or CreditSettings.load()
    others = Applicant.objects.filter(ticket=ticket).exclude(typeofapplicant=1).count()
    return settings.primary_expenditure + others * settings.other_applicant_expenditure


def debt_service_ratio(installments, income):
    """Monthly installments as a percentage of monthly income, 3 decimals."""
    if not income:
        return Decimal(0)
    return (Decimal(installments) * 100 / Decimal(income)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)


def update_repayment(ticket):
    """DSR (highest and average payments) and net surplus after payments and living costs."""
    loan = LoanDetail.objects.get(ticket=ticket)
    detail, _created = CreditAssessment.objects.get_or_create(ticket=ticket)
    income = detail.monthly_income
    if income:
        detail.dsr_high = debt_service_ratio(loan.highest_installment + detail.exist_highest_installment, income)
        detail.dsr_avg = debt_service_ratio(loan.average_installment + detail.exist_average_installment, income)
        detail.nst = income - detail.exist_highest_installment - loan.highest_installment - detail.expenditure
    detail.save(update_fields=['dsr_high', 'dsr_avg', 'nst'])
    return detail


def set_expenditure(ticket, amount, settings=None):
    """
    Use the entered living cost if it exceeds the default, else the default.
    Returns True if the entered amount was used.
    """
    default = default_expenditure(ticket, settings)
    detail, _created = CreditAssessment.objects.get_or_create(ticket=ticket)
    detail.expenditure = amount if amount > default else default
    detail.save(update_fields=['expenditure'])
    update_repayment(ticket)
    return amount > default


@transaction.atomic
def recalc_credit_summary(ticket, settings=None):
    """Everything the credit review summary shows, recalculated in one transaction."""
    settings = settings or CreditSettings.load()
    recalc_income(ticket, settings)
    recalc_existing_installments(ticket)
    detail = CreditAssessment.objects.get(ticket=ticket)
    if not detail.expenditure:
        detail.expenditure = default_expenditure(ticket, settings)
        detail.save(update_fields=['expenditure'])
    return update_repayment(ticket)


def score_band(score, settings=None):
    """'Band N': one band per band_size points, starting at Band 1, capped at max_band."""
    settings = settings or CreditSettings.load()
    band = int(Decimal(score) // settings.band_size) + 1
    return 'Band %d' % max(1, min(band, settings.max_band))


@transaction.atomic
def create_application(user):
    """
    A new draft application submitted by `user`, with its empty loan, credit
    decision, contract, collateral and credit-detail records. The title is AP<mm><yy><username><id+1000>;
    it is set after the insert so that the id, and so the title, is unique.
    """
    from datetime import timedelta

    from lwf.models import CollaManager, CreditDecision, LoanContract, Ticket

    now = timezone.now()
    ticket = Ticket.objects.create(
        title='new-%s' % now.timestamp(), submitter=user, assigned_to=user, due_date=now + timedelta(days=3),
        status=Ticket.OPEN_STATUS)
    ticket.title = 'AP%s%s%d' % (now.strftime('%m%y'), user.username, ticket.id + 1000)
    ticket.save(update_fields=['title'])
    LoanDetail.objects.create(ticket=ticket)
    CreditDecision.objects.create(ticket=ticket)
    LoanContract.objects.create(ticket=ticket)
    CollaManager.objects.create(ticket=ticket)
    CreditAssessment.objects.create(ticket=ticket)
    return ticket


# Collateral type implied by the loan product code (see Product): 6 auto loan,
# 2 and 5 property under development (sale contract), 1, 3 and 4 property with a title deed.
COLLATERAL_TYPE_BY_PRODUCT = {6: 1, 2: 3, 5: 3, 1: 2, 3: 2, 4: 2}


def apply_loan_change(loan):
    """After the loan request changes: installments, and the collateral type its product implies."""
    from lwf.models import CollaManager

    update_loan_installments(loan)
    colla_type = COLLATERAL_TYPE_BY_PRODUCT.get(loan.product)
    if colla_type:
        CollaManager.objects.filter(ticket=loan.ticket_id).update(colla_type=colla_type)


def normalize_applicant(applicant):
    """Fill the unaccented upper-case copies of the name and addresses that documents use."""
    from lwf.calculations import ascii_upper

    applicant.name_en = ascii_upper(applicant.name_vn)
    applicant.permanent_address = ascii_upper(applicant.permanent_address_vn)
    applicant.temporary_address = ascii_upper(applicant.temporary_address_vn)


# Bureau and account inputs a CED officer enters for CRR scoring (ScoreDetail fields).
SCORING_INPUTS = ('age_borrower_acc', 'conduct_acc', 'where_report', 'num_CI', 'no12_Defaults', 'no60_Defaults')


@transaction.atomic
def score_application(ticket, bureau, settings=None):
    """
    CRR score of an application. `bureau` holds the SCORING_INPUTS entered by
    CED; the other inputs come from the primary applicant, the loan and the
    credit assessment. Returns (score, band, points per field).
    """
    from lwf import scoring
    from lwf.models import ScoreDetail, ScoreMatrixVersion

    version = ScoreMatrixVersion.active()
    if version is None:
        raise ValidationError(_('No active score matrix version: an administrator must activate one.'))
    assessment = recalc_income(ticket, settings)
    applicants = Applicant.objects.filter(ticket=ticket)
    primary = applicants.filter(typeofapplicant=1).first()
    loan = LoanDetail.objects.get(ticket=ticket)
    score_detail, _created = ScoreDetail.objects.get_or_create(ticket=ticket)
    for name, value in bureau.items():
        setattr(score_detail, name, value)
    if not score_detail.where_report:
        score_detail.num_CI = score_detail.no12_Defaults = score_detail.no60_Defaults = 0
    score_detail.age = primary.age if primary else None
    score_detail.marital = primary.marital if primary else None
    score_detail.typeofhouse = primary.typehouse if primary else None
    score_detail.edulvl = primary.edulvl if primary else None
    score_detail.resstat = primary.resstat if primary else None
    score_detail.numborrow = applicants.count()
    score_detail.length_in_service = assessment.lengthinservice
    score_detail.employment_type = assessment.employment_type
    score_detail.monthly_average = assessment.monthly_income
    score_detail.dsr = int(assessment.dsr_high or 0)
    score_detail.loan_term = loan.loan_tenor
    score_detail.loan_value_ratio = score_detail.loan_moa = loan.loan_moa
    score_detail.loan_amount = loan.loanamount
    # Inputs the old scoring always set to 1 (one mortgagor, one income source, ...).
    score_detail.mortgagor = score_detail.source_income = 1
    score_detail.property_type = score_detail.collateral_type = score_detail.mortgage_loan_type = 1
    score_detail.matrix_version, score_detail.scored_at = version, timezone.now()
    score_detail.save()

    score, points = scoring.score(scoring_values(score_detail), version.rows.all())
    assessment.crr_score = score
    assessment.crr_band = score_band(score, settings)
    assessment.save(update_fields=['crr_score', 'crr_band'])
    return score, assessment.crr_band, points


def scoring_values(score_detail):
    """The inputs of a ScoreDetail that the score matrix scores."""
    return {field.name: field.value_from_object(score_detail) for field in score_detail._meta.fields
            if field.name not in ('id', 'ticket', 'matrix_version', 'scored_at')}


def score_points(ticket):
    """Points per criterion of the application's stored inputs, with the matrix version that scored them."""
    from lwf import scoring
    from lwf.models import ScoreDetail, ScoreMatrixVersion

    score_detail = ScoreDetail.objects.get(ticket=ticket)
    version = score_detail.matrix_version or ScoreMatrixVersion.active()
    return scoring.score(scoring_values(score_detail), version.rows.all() if version else [])[1]