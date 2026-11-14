"""Test helpers."""
import datetime

from lwf.completeness import REQUIRED_DOCUMENT_GROUPS
from lwf.models import (Applicant, AttachDocument, CollaManager, CreditAssessment, LoanDetail, LoanEarlyRepayment,
                        LoanScheme)


def complete_application(ticket):
    """Fill what the completeness checks need, so Sale can send the application on."""
    primary, _created = Applicant.objects.get_or_create(ticket=ticket, typeofapplicant=1, defaults={
        'name_vn': 'Nguyễn Văn Test', 'cid': '079000000001'})
    primary.dob = primary.dob or datetime.date(1990, 1, 1)
    primary.save()
    fee = LoanEarlyRepayment.objects.create(description='Test', early_rate1=3, early_rate2=2, early_rate3=1,
                                            early_rate4=0)
    scheme = LoanScheme.objects.create(package='TEST', margin=2, normal=10, early_payment=fee,
                                       datefrom=datetime.date(2026, 1, 1))
    loan, _ = LoanDetail.objects.get_or_create(ticket=ticket)
    loan.product = loan.product or 1
    loan.loanamount, loan.loan_tenor, loan.loan_pricing_scheme = 1_000_000_000, 240, scheme
    loan.save()
    CollaManager.objects.create(ticket=ticket, spa_or_estimated=2_000_000_000)
    CreditAssessment.objects.update_or_create(ticket=ticket, defaults={'monthly_income': 50_000_000})
    for group in REQUIRED_DOCUMENT_GROUPS:
        # Only the name: the tests never open the file.
        AttachDocument.objects.create(ticket=ticket, related_data=group, filename='doc%d.pdf' % group,
                                      file='lwf/attachments/test/doc%d.pdf' % group)
