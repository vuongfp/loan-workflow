import datetime

from django.test import TestCase
from django.utils import translation

from lwf import policy
from lwf.models import Applicant, CreditAssessment, CreditPolicy, LoanDetail, Ticket


class PolicyTests(TestCase):
    def setUp(self):
        CreditPolicy.objects.all().delete()
        CreditPolicy.objects.create(max_dsr=60, max_ltv=70, max_tenor=240, max_age_at_maturity=65,
                                    min_monthly_income=10_000_000, min_net_surplus=3_000_000,
                                    max_loan_amount=5_000_000_000)
        CreditPolicy.objects.create(product_code=6, max_tenor=84, max_ltv=80)
        self.ticket = Ticket.objects.create(title='AP1')
        today = datetime.date.today()
        Applicant.objects.create(ticket=self.ticket, typeofapplicant=1, name_vn='A', cid='1',
                                 dob=today.replace(year=today.year - 50))
        self.loan = LoanDetail.objects.create(ticket=self.ticket, product=1, loanamount=2_000_000_000,
                                              loan_tenor=300, loan_moa=75)
        CreditAssessment.objects.create(ticket=self.ticket, monthly_income=40_000_000, dsr_high=65, nst=2_000_000)

    def rules(self):
        with translation.override('en'):
            return {breach.rule: breach.deviation for breach in policy.breaches(self.ticket)}

    def test_breaches_name_the_deviation_to_declare(self):
        self.assertEqual(self.rules(), {'Tenor': 101, 'Loan to value': 102, 'Age at maturity': 104, 'DSR': 107,
                                        'Net surplus after payments': 107})
        self.assertEqual(policy.suggested_deviations(self.ticket), [101, 102, 104, 107])
        LoanDetail.objects.filter(pk=self.loan.pk).update(deviation1=101, deviation2=107)
        self.assertEqual(policy.suggested_deviations(self.ticket), [102, 104])

    def test_a_product_policy_replaces_the_default(self):
        LoanDetail.objects.filter(pk=self.loan.pk).update(product=6, loan_tenor=72, loan_moa=78)
        self.assertEqual(self.rules(), {})   # the auto loan policy has no DSR or income limits
