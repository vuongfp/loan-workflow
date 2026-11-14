"""Credit memo of a loan application as a PDF (xhtml2pdf)."""
import io
import os

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa
from xhtml2pdf.config.resources import ResourceAccessPolicy

from lwf import policy
from lwf.models import Applicant, CollaManager, Condition, CreditDecision, FollowUp, LoanDetail, CreditAssessment

# A TrueType font with Vietnamese glyphs; the PDF base fonts have none.
FONT_DIR = os.environ.get('MEMO_FONT_DIR', '/usr/share/fonts/truetype/dejavu')


def memo_context(ticket):
    loan = LoanDetail.objects.select_related('loan_pricing_scheme').get(ticket=ticket)
    return {
        'ticket': ticket,
        'loan': loan,
        'product': loan.get_product_display(),
        'subproduct': loan.get_subproduct_display(),
        'applicants': Applicant.objects.filter(ticket=ticket).order_by('typeofapplicant', 'id'),
        'collaterals': CollaManager.objects.filter(ticket=ticket).select_related('project_name', 'car_dealer'),
        'detail': CreditAssessment.objects.filter(ticket=ticket).first(),
        'decision': CreditDecision.objects.filter(ticket=ticket).first(),
        'policy_breaches': policy.breaches(ticket),
        'conditions': Condition.objects.filter(ticket=ticket),
        'history': FollowUp.objects.filter(ticket=ticket).select_related('user').order_by('date'),
        'lender': settings.LENDER,
        'printed': timezone.localtime(),
        'font_regular': os.path.join(FONT_DIR, 'DejaVuSans.ttf'),
        'font_bold': os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'),
    }


def credit_memo_pdf(ticket):
    """PDF bytes of the credit memo."""
    return render_pdf('lwf/memo/credit_memo.html', memo_context(ticket), ticket.title)


def credit_contract_pdf(doc):
    """PDF bytes of a loan contract (CraDocInfo): the parties section, filled from the application."""
    borrower = Applicant.objects.filter(ticket=doc.ticket_id, typeofapplicant=1).first()
    context = {'doc': doc, 'borrower': borrower, 'lender': settings.LENDER,
               'font_regular': os.path.join(FONT_DIR, 'DejaVuSans.ttf'),
               'font_bold': os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')}
    return render_pdf('lwf/memo/credit_contract.html', context, doc.contract_number or doc.pk)


def render_pdf(template, context, label):
    html = render_to_string(template, context)
    output = io.BytesIO()
    # The memo includes text users typed: render with every resource limit on,
    # no network access, and local reads confined to the font directory.
    policy = ResourceAccessPolicy.server(base_dir=FONT_DIR, allow_remote=False)
    result = pisa.CreatePDF(html, dest=output, encoding='utf-8', resource_policy=policy)
    if result.err:
        raise RuntimeError('Could not build the PDF %s for %s' % (template, label))
    return output.getvalue()
