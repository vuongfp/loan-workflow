"""
Contracts as Word files: a .docx template (ContractTemplate, or the default in
lwf/contract_templates/) filled with the application's data by docxtpl (Jinja
placeholders such as {{ borrower.name }}). PLACEHOLDERS documents what a
template can use.
"""
import io
import os

from django.conf import settings
from django.utils import timezone

from lwf import words
from lwf.models import Applicant, CollaManager, ContractTemplate, CraLoanSaleParty, LoanContract, LoanDetail

DEFAULT_DIR = os.path.join(os.path.dirname(__file__), 'contract_templates')
DEFAULT_FILES = {1: 'credit_agreement.docx', 2: 'mortgage_agreement.docx', 3: 'tripartite_agreement.docx',
                 4: 'valuation_minutes.docx'}

PLACEHOLDERS = [
    ('lender.name, lender.address, lender.registration', 'The bank (settings LENDER_*)'),
    ('contract.number, contract.sign_date, contract.signer, contract.position', 'This contract document'),
    ('application.number', 'Application number (DS....)'),
    ('borrower.name, borrower.id_number, borrower.id_date, borrower.id_place, borrower.dob, '
     'borrower.permanent_address, borrower.current_address', 'Primary applicant'),
    ('co_borrowers (list, same fields as borrower)', 'Other applicants'),
    ('loan.amount, loan.amount_words, loan.credit_limit, loan.credit_limit_words, loan.disbursement_amount, '
     'loan.interest_rate, loan.margin, loan.early_repayment_fee, loan.tenor, loan.purpose, '
     'loan.disbursement_method, loan.conditions', 'Loan contract terms (CRA)'),
    ('collaterals (list): type, address, value, value_words, land_plot, land_map, land_area, certificate, '
     'certificate_number, certificate_date, certificate_place, car_brand, car_body_no, car_machine_no',
     'Collaterals with their legal data'),
    ('sellers (list): name, birth_year, id_number, id_place, address', 'Sale parties'),
    ('today', 'Date the file is made'),
]


def _date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def _money(value):
    return '{:,}'.format(value) if value else ''


def _person(applicant):
    return {
        'name': applicant.name_vn, 'id_number': applicant.cid, 'id_date': _date(applicant.cra_id_date),
        'id_place': applicant.cra_id_place or '', 'dob': _date(applicant.dob),
        'permanent_address': applicant.cra_permanent_address or applicant.permanent_address_vn or '',
        'current_address': applicant.cra_temporary_address or applicant.temporary_address_vn or '',
    }


def _collateral(collateral):
    legal = getattr(collateral, 'contract', None)
    value = collateral.spa_or_estimated or collateral.car_spa_value or 0
    data = {'type': collateral.get_colla_type_display() or '', 'value': _money(value),
            'value_words': words.amount_words(value), 'address': collateral.fulladdress_vn or '',
            'car_brand': collateral.car_brand or ''}
    if legal:
        data.update({
            'address': legal.fulladdress or data['address'], 'land_plot': legal.land_plot or '',
            'land_map': legal.land_map or '', 'land_area': legal.land_area or '',
            'certificate': legal.get_gcn_name_display() or '', 'certificate_number': legal.issue_no or '',
            'certificate_date': _date(legal.gcn_issue_date), 'certificate_place': legal.gcn_issue_place or '',
            'car_brand': legal.car_brand or data['car_brand'], 'car_body_no': legal.car_body_no or '',
            'car_machine_no': legal.car_machine_no or '',
        })
    return data


def context(doc):
    ticket = doc.ticket
    applicants = list(Applicant.objects.filter(ticket=ticket).order_by('typeofapplicant', 'pk'))
    primary = next((a for a in applicants if a.typeofapplicant == 1), None)
    request = LoanDetail.objects.filter(ticket=ticket).first()
    terms = LoanContract.objects.filter(ticket=ticket).first()
    amount = (terms and terms.loan_amount) or (request and request.loanamount) or 0
    return {
        'lender': settings.LENDER,
        'contract': {'number': doc.contract_number or '', 'sign_date': _date(doc.sign_date),
                     'signer': doc.signer or '', 'position': doc.position or ''},
        'application': {'number': ticket.title},
        'borrower': _person(primary) if primary else {},
        'co_borrowers': [_person(a) for a in applicants if a is not primary],
        'loan': {
            'amount': _money(amount), 'amount_words': words.amount_words(amount),
            'credit_limit': _money(terms.credit_limit) if terms else '',
            'credit_limit_words': (terms.credit_limit_in_words or words.amount_words(terms.credit_limit))
                                  if terms else '',
            'disbursement_amount': _money(terms.disbursement_amount) if terms else '',
            'interest_rate': (terms.interest_rate or '') if terms else '',
            'margin': (terms.margin or '') if terms else '',
            'early_repayment_fee': (terms.early_repayment_fee or '') if terms else '',
            'tenor': (terms and terms.tenor) or (request and request.loan_tenor) or '',
            'purpose': (terms and terms.purpose) or (request.get_purpose_display() if request else ''),
            'disbursement_method': (terms.disbursement_method or '') if terms else '',
            'conditions': (terms.conditions or '') if terms else '',
        },
        'collaterals': [_collateral(c) for c in
                        CollaManager.objects.filter(ticket=ticket).select_related('contract').order_by('pk')],
        'sellers': [{'name': p.cra_salepart_name or '', 'birth_year': p.cra_salepart_year or '',
                     'id_number': p.cra_salepart_id or '', 'id_place': p.cra_salepart_idplace or '',
                     'address': p.cra_salepart_peraddress or ''}
                    for p in CraLoanSaleParty.objects.filter(ticket=ticket)],
        'today': _date(timezone.localdate()),
    }


def template_path(contract_type):
    uploaded = ContractTemplate.objects.filter(contract_type=contract_type, is_active=True).first()
    if uploaded:
        return uploaded.file.path
    return os.path.join(DEFAULT_DIR, DEFAULT_FILES.get(contract_type, DEFAULT_FILES[1]))


def contract_docx(doc):
    """The contract document as .docx bytes."""
    from docxtpl import DocxTemplate

    template = DocxTemplate(template_path(doc.contract_type))
    template.render(context(doc), autoescape=True)
    output = io.BytesIO()
    template.save(output)
    return output.getvalue()
