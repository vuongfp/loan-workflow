from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from lwf import services
from lwf.models import (Applicant, BusinessIncome, CicCreditCard, CicUnSecureLoan, CollaManager,
                        CreditSettings, LoanDetail, SalaryIncome, Ticket, CreditAssessment)

User = get_user_model()


class CalculationTests(SimpleTestCase):

    def test_loan_installments_equal_principal(self):
        # 120m over 12 months at 12%/year: 10m principal a month, 1% interest a month.
        self.assertEqual(services.loan_installments(120000000, 12, Decimal('12')),
                         (11200000, 10100000, 10650000))

    def test_loan_installments_without_tenor(self):
        self.assertEqual(services.loan_installments(120000000, 0, Decimal('12')), (0, 0, 0))

    def test_segmentation(self):
        settings = CreditSettings()
        self.assertEqual(services.segmentation(20000000, 5000000, 0, 0, settings),
                         (services.SAL, services.EMPLOYMENT_SALARY))
        # Salary is most of the income but under the 15m threshold.
        self.assertEqual(services.segmentation(10000000, 2000000, 0, 0, settings)[0], services.SEC)
        self.assertEqual(services.segmentation(0, 5000000, 0, 9000000, settings)[0], services.RTL)
        self.assertEqual(services.segmentation(0, 3000000, 5000000, 0, settings)[0], services.SHH)

    def test_score_band(self):
        settings = CreditSettings()
        cases = {0: 'Band 1', 99: 'Band 1', 100: 'Band 2', Decimal('525.14'): 'Band 6',
                 899: 'Band 9', 950: 'Band 10', 1500: 'Band 10'}
        for score, band in cases.items():
            self.assertEqual(services.score_band(score, settings), band, score)

    def test_debt_service_ratio(self):
        self.assertEqual(services.debt_service_ratio(3000000, 9000000), Decimal('33.333'))
        self.assertEqual(services.debt_service_ratio(3000000, 0), 0)


class CreditSummaryTests(TestCase):

    def setUp(self):
        user = User.objects.create_user('sale', is_staff=True)
        self.ticket = Ticket.objects.create(title='AP1', submitter=user)
        self.primary = Applicant.objects.create(ticket=self.ticket, typeofapplicant=1)
        self.co = Applicant.objects.create(ticket=self.ticket, typeofapplicant=2)
        LoanDetail.objects.create(ticket=self.ticket, loanamount=120000000, loan_tenor=12,
                                  highest_installment=11200000, average_installment=10650000)
        CollaManager.objects.create(ticket=self.ticket)

    def test_income_totals_and_segment(self):
        SalaryIncome.objects.create(applicant=self.primary, monthamt=1, fix_m1=18000000,
                                    varmonthamt=1, var_m1=2000000, length_in_service=36)
        # 6.25m a month of VAT turnover at a 100% margin: 6.25m x 0.8 = 5m net.
        BusinessIncome.objects.create(applicant=self.co, vat_period=1, vat_amount=6250000,
                                      year3_sales_turnover=75000000, EBITDAmargin=100, years=4)
        detail = services.recalc_income(self.ticket)
        self.assertEqual((detail.net_income, detail.biz_income, detail.monthly_income),
                         (20000000, 5000000, 25000000))
        self.assertEqual((detail.segmentation, detail.lengthinservice), (services.SAL, 36))
        self.primary.refresh_from_db()
        self.assertEqual(self.primary.total, 20000000)

    def test_business_income_only_on_co_applicant_does_not_crash(self):
        # The old calcIncome crashed here: the primary applicant has no business record.
        BusinessIncome.objects.create(applicant=self.co, vat_period=1, vat_amount=10000000,
                                      year3_sales_turnover=120000000, EBITDAmargin=100, years=4)
        detail = services.recalc_income(self.ticket)
        self.assertEqual((detail.segmentation, detail.lengthinservice), (services.SEC, 0))

    def test_existing_installments(self):
        CicUnSecureLoan.objects.create(applicant=self.primary, m1=1000000, m2=1000000, m3=1000000)
        # 5% minimum payment on a 10m average balance.
        CicCreditCard.objects.create(applicant=self.co, bm1=10000000, bm2=10000000, bm3=10000000,
                                     bm4=10000000, bm5=10000000, bm6=10000000)
        detail = services.recalc_existing_installments(self.ticket)
        self.assertEqual((detail.exist_highest_installment, detail.exist_average_installment), (1500000, 1500000))

    def test_summary_sets_default_expenditure_and_ratios(self):
        SalaryIncome.objects.create(applicant=self.primary, monthamt=1, fix_m1=30000000)
        detail = services.recalc_credit_summary(self.ticket)
        self.assertEqual(detail.expenditure, 5000000 + 4420000)
        self.assertEqual(detail.dsr_high, Decimal('37.333'))
        self.assertEqual(detail.nst, 30000000 - 11200000 - 9420000)

    def test_entered_expenditure_below_default_is_raised_to_default(self):
        SalaryIncome.objects.create(applicant=self.primary, monthamt=1, fix_m1=30000000)
        services.recalc_credit_summary(self.ticket)
        self.assertFalse(services.set_expenditure(self.ticket, 1000000))
        self.assertEqual(CreditAssessment.objects.get(ticket=self.ticket).expenditure, 9420000)
        self.assertTrue(services.set_expenditure(self.ticket, 12000000))
        self.assertEqual(CreditAssessment.objects.get(ticket=self.ticket).expenditure, 12000000)

    def test_settings_change_default_expenditure(self):
        settings = CreditSettings.load()
        settings.primary_expenditure = 6000000
        settings.save()
        self.assertEqual(services.default_expenditure(self.ticket), 6000000 + 4420000)
