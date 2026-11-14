"""
Figures derived from what a user enters on one income or credit record.

These used to be computed by JavaScript in the AJAX forms and saved as sent;
the models now compute them in save(). Amounts are whole VND.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

CREDIT_CARD_MIN_PAYMENT = Decimal('0.05')    # minimum monthly payment, share of the balance
RENTAL_MAX_MARGIN = 90                       # percent of the rent counted as income
BUSINESS_TURNOVER_HAIRCUT = Decimal('0.8')   # share of monthly turnover counted before margin


def whole(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _num(value):
    return Decimal(value or 0)


def average(values, months):
    """Sum of the first `months` values divided by `months` (0 when no months)."""
    months = int(months or 0)
    if months <= 0:
        return 0
    return whole(sum(_num(v) for v in values[:months]) / months)


def salary(record):
    fixed = [getattr(record, 'fix_m%d' % i) for i in range(1, 13)]
    variable = [getattr(record, 'var_m%d' % i) for i in range(1, 13)]
    # The months entered are counted from the first one, as on the old form.
    record.fix_avg = whole(sum(_num(v) for v in fixed) / record.monthamt) if record.monthamt else 0
    record.var_avg = whole(sum(_num(v) for v in variable) / record.varmonthamt) if record.varmonthamt else 0
    record.avg = record.fix_avg + record.var_avg


def household(record):
    record.monthly_average = average([getattr(record, 'm%d' % i) for i in range(1, 7)], record.mamt)
    record.netincome = whole(_num(record.monthly_average) * _num(record.margin) / 100)


def business(record):
    for year in (1, 2, 3):
        paid_up = _num(getattr(record, 'year%d_paidup_capital' % year))
        retained = _num(getattr(record, 'year%d_retained_earning' % year))
        intangible = _num(getattr(record, 'year%d_intangible_assets' % year))
        setattr(record, 'year%d_tangible_net_worth' % year, whole(paid_up + retained - intangible))
    period = int(record.vat_period or 0)
    record.vat_monthly = whole(_num(record.vat_amount) / period) if period else 0
    record.bank_statement_monthly = whole(_num(record.bank_statement_amount) / period) if period else 0
    record.year3_net_sales_turnover = whole(_num(record.year3_sales_turnover) / 12)
    record.monthly_average = min(record.vat_monthly, record.year3_net_sales_turnover)
    record.netincome = whole(_num(record.monthly_average) * BUSINESS_TURNOVER_HAIRCUT * _num(record.EBITDAmargin) / 100)


def rental(record):
    margin = min(_num(record.proxy_margin), RENTAL_MAX_MARGIN)
    record.proxy_margin = int(margin)
    record.net_income = whole(_num(record.leasing_price) * margin / 100)


def secured_loan(record):
    """Equal-principal loan; while still being disbursed, interest is on the full amount."""
    tenor = int(record.loan_tenor or 0)
    if not tenor:
        record.highest_installment = record.averageinstallment = 0
        return
    monthly_rate = _num(record.interest_rate) / 1200
    principal_part = _num(record.original_amount) / tenor
    balance = _num(record.original_amount) if record.progressive_disbursement else _num(record.outstanding_loan)
    highest = principal_part + balance * monthly_rate
    lowest = principal_part * (1 + monthly_rate)
    record.highest_installment = whole(highest)
    record.averageinstallment = whole((highest + lowest) / 2)


def unsecured_loan(record):
    record.installment = average([record.m1, record.m2, record.m3], 3)


def overdraft(record):
    record.installment = whole(_num(record.interest_rate) * _num(record.outstanding_loan) / 1200)


def credit_card(record):
    record.avg_balance_6m = average([getattr(record, 'bm%d' % i) for i in range(1, 7)], 6)
    record.highest_installment = record.averageinstallment = whole(_num(record.avg_balance_6m) * CREDIT_CARD_MIN_PAYMENT)


VIETNAMESE_ACCENTS = {
    '[àáảãạăắằẵặẳâầấậẫẩ]': 'a',
    '[đ]': 'd',
    '[èéẻẽẹêềếểễệ]': 'e',
    '[ìíỉĩị]': 'i',
    '[òóỏõọôồốổỗộơờớởỡợ]': 'o',
    '[ùúủũụưừứửữự]': 'u',
    '[ỳýỷỹỵ]': 'y',
}


def ascii_upper(text):
    """Vietnamese text without accents, upper case: 'Nguyễn Văn A' -> 'NGUYEN VAN A'."""
    output = text or ''
    for pattern, replacement in VIETNAMESE_ACCENTS.items():
        output = re.sub(pattern, replacement, output)
        output = re.sub(pattern.upper(), replacement.upper(), output)
    return output.upper()
