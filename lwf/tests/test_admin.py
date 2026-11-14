from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from lwf import calculations
from lwf.access import CED, CRA, SALE, accessible_tickets, editable_sections
from lwf.models import Applicant, CollaManager, CollateralContract, CreditDecision, FollowUp, LoanDetail, SalaryIncome, Ticket, CreditAssessment

User = get_user_model()


class CalculationTests(SimpleTestCase):

    def test_salary_averages_over_months_counted(self):
        record = SimpleNamespace(monthamt=3, varmonthamt=2, **{'fix_m%d' % i: 0 for i in range(1, 13)},
                                 **{'var_m%d' % i: 0 for i in range(1, 13)})
        record.fix_m1, record.fix_m2, record.fix_m3 = 10000000, 11000000, 12000000
        record.var_m1, record.var_m2 = 1000000, 3000000
        calculations.salary(record)
        self.assertEqual((record.fix_avg, record.var_avg, record.avg), (11000000, 2000000, 13000000))

    def test_household_net_income_uses_margin(self):
        record = SimpleNamespace(mamt=2, m1=20000000, m2=30000000, m3=0, m4=0, m5=0, m6=0, margin=20)
        calculations.household(record)
        self.assertEqual((record.monthly_average, record.netincome), (25000000, 5000000))

    def test_business_takes_lower_of_vat_and_annual_turnover(self):
        record = SimpleNamespace(vat_period=3, vat_amount=300000000, bank_statement_amount=330000000,
                                 year3_sales_turnover=960000000, EBITDAmargin=10,
                                 **{'year%d_%s' % (y, f): 0 for y in (1, 2, 3)
                                    for f in ('paidup_capital', 'retained_earning', 'intangible_assets')})
        calculations.business(record)
        # VAT: 100m a month; annual: 80m a month; net = 80m x 0.8 x 10%.
        self.assertEqual((record.monthly_average, record.netincome), (80000000, 6400000))

    def test_rental_margin_is_capped_at_90_percent(self):
        record = SimpleNamespace(leasing_price=10000000, proxy_margin=95)
        calculations.rental(record)
        self.assertEqual((record.proxy_margin, record.net_income), (90, 9000000))

    def test_secured_loan_installments(self):
        record = SimpleNamespace(original_amount=120000000, loan_tenor=12, interest_rate=12,
                                 outstanding_loan=60000000, progressive_disbursement=False)
        calculations.secured_loan(record)
        # First month on the outstanding 60m: 10m + 0.6m; last month 10m + 0.1m.
        self.assertEqual((record.highest_installment, record.averageinstallment), (10600000, 10350000))

    def test_overdraft_and_credit_card(self):
        overdraft = SimpleNamespace(interest_rate=12, outstanding_loan=50000000)
        calculations.overdraft(overdraft)
        self.assertEqual(overdraft.installment, 500000)
        card = SimpleNamespace(**{'bm%d' % i: 6000000 for i in range(1, 7)})
        calculations.credit_card(card)
        self.assertEqual((card.avg_balance_6m, card.highest_installment), (6000000, 300000))

    def test_ascii_upper(self):
        self.assertEqual(calculations.ascii_upper('Nguyễn Văn Đức'), 'NGUYEN VAN DUC')


class RoleTestCase(TestCase):

    def setUp(self):
        self.sale = self.user('sale', 'SaleTeam')
        self.ced = self.user('ced', 'CEDOfficer')
        self.cra = self.user('cra', 'CRAOfficer')
        self.other = self.user('other', 'SaleTeam')
        self.ticket = Ticket.objects.create(title='AP1', submitter=self.sale, ced=self.ced,
                                            cra=self.cra, status=Ticket.OPEN_STATUS)
        self.loan = LoanDetail.objects.create(ticket=self.ticket, loanamount=100000000)
        CreditDecision.objects.create(ticket=self.ticket)
        CollaManager.objects.create(ticket=self.ticket)
        CreditAssessment.objects.create(ticket=self.ticket)
        self.applicant = Applicant.objects.create(ticket=self.ticket, typeofapplicant=1, name_vn='Trần Thị B',
                                                  cid='079190000001')

    @staticmethod
    def user(name, group):
        user = User.objects.create_user(name, is_staff=True)
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    def set_status(self, status):
        Ticket.objects.filter(pk=self.ticket.pk).update(status=status)
        self.ticket.refresh_from_db()


class EditRuleTests(RoleTestCase):

    def test_sections_follow_role_and_status(self):
        self.assertEqual(editable_sections(self.sale, self.ticket), {SALE})
        self.assertEqual(editable_sections(self.ced, self.ticket), set())
        self.set_status(Ticket.VERIFY_STATUS)
        self.assertEqual(editable_sections(self.sale, self.ticket), set())
        self.assertEqual(editable_sections(self.ced, self.ticket), {CED})
        self.set_status(Ticket.DOCSPREP_STATUS)
        self.assertEqual(editable_sections(self.cra, self.ticket), {CRA})

    def test_accessible_tickets_matches_roles(self):
        self.assertIn(self.ticket, accessible_tickets(self.sale))
        self.assertNotIn(self.ticket, accessible_tickets(self.other))


class TicketAdminTests(RoleTestCase):

    def change_url(self):
        return reverse('admin:lwf_ticket_change', args=[self.ticket.pk])

    def test_list_shows_only_accessible_applications(self):
        Ticket.objects.create(title='AP-OTHER', submitter=self.other)
        self.client.force_login(self.sale)
        response = self.client.get(reverse('admin:lwf_ticket_changelist'))
        self.assertContains(response, 'AP1')
        self.assertNotContains(response, 'AP-OTHER')

    def test_outsider_cannot_open_application(self):
        self.client.force_login(self.other)
        response = self.client.get(self.change_url())
        self.assertNotEqual(response.status_code, 200)

    def test_sale_edits_loan_request_but_not_credit_decision(self):
        self.client.force_login(self.sale)
        form = self.client.get(self.change_url()).context['adminform'].form
        inline_forms = {f.formset.model: f.formset for f in
                        self.client.get(self.change_url()).context['inline_admin_formsets']}
        loan_form = inline_forms[LoanDetail].forms[0]
        self.assertIn('loanamount', loan_form.fields)
        self.assertNotIn('approved_amount', inline_forms[CreditDecision].forms[0].fields)
        self.assertNotIn('status', form.fields)

    def test_ced_sees_application_read_only_while_sale_edits(self):
        self.client.force_login(self.ced)
        response = self.client.get(self.change_url())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_change_permission'])

    def test_create_application_from_admin(self):
        self.client.force_login(self.sale)
        self.assertEqual(self.client.get(reverse('admin:lwf_ticket_add')).status_code, 200)
        response = self.client.post(reverse('admin:lwf_ticket_add'))
        ticket = Ticket.objects.exclude(pk=self.ticket.pk).get(submitter=self.sale)
        self.assertRedirects(response, reverse('admin:lwf_ticket_change', args=[ticket.pk]))
        self.assertTrue(LoanDetail.objects.filter(ticket=ticket).exists())
        self.assertTrue(ticket.title.startswith('AP'))

    def test_only_sale_team_creates_applications(self):
        self.client.force_login(self.ced)
        self.assertEqual(self.client.post(reverse('admin:lwf_ticket_add')).status_code, 403)

    def test_applications_cannot_be_deleted(self):
        superuser = User.objects.create_superuser('root', password=None)
        self.client.force_login(superuser)
        response = self.client.get(reverse('admin:lwf_ticket_delete', args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 403)


class ApplicantAdminTests(RoleTestCase):

    def test_saving_income_recalculates_application_totals(self):
        self.client.force_login(self.sale)
        url = reverse('admin:lwf_applicant_change', args=[self.applicant.pk])
        response = self.client.get(url)
        data = {}
        for formset in response.context['inline_admin_formsets']:
            management = formset.formset.management_form
            for name, field in management.fields.items():
                data['%s-%s' % (formset.formset.prefix, name)] = management.initial.get(name, field.initial)
        form = response.context['adminform'].form
        for name, field in form.fields.items():
            value = form.initial.get(name)
            if value is not None:
                data[name] = value.isoformat() if hasattr(value, 'isoformat') else value
        prefix = [f.formset.prefix for f in response.context['inline_admin_formsets']
                  if f.formset.model is SalaryIncome][0]
        # Three months of fixed pay, no variable pay.
        data.update({'%s-TOTAL_FORMS' % prefix: 1, '%s-0-monthamt' % prefix: 3,
                     '%s-0-fix_m1' % prefix: '20,000,000', '%s-0-fix_m2' % prefix: '21,000,000',
                     '%s-0-fix_m3' % prefix: '22,000,000', '%s-0-varmonthamt' % prefix: 3})
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.context and (
            response.context['adminform'].form.errors,
            [(f.formset.prefix, f.formset.errors, f.formset.non_form_errors())
             for f in response.context['inline_admin_formsets']]))
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.total, 21000000)
        self.assertEqual(self.applicant.name_en, 'TRAN THI B')
        self.assertEqual(CreditAssessment.objects.get(ticket=self.ticket).monthly_income, 21000000)


class CollateralContractTests(RoleTestCase):
    def test_cra_fills_collateral_contract_data_on_the_collateral_page(self):
        collateral = CollaManager.objects.create(ticket=self.ticket)
        self.set_status(Ticket.DOCSPREP_STATUS)
        self.client.force_login(self.cra)
        url = reverse('admin:lwf_collamanager_change', args=[collateral.pk])
        formsets = {f.formset.model: f.formset for f in self.client.get(url).context['inline_admin_formsets']}
        self.assertIn('gcn_name', formsets[CollateralContract].forms[0].fields)


class WorkflowHistoryTests(RoleTestCase):
    def test_sale_sees_the_workflow_history_of_their_application(self):
        FollowUp.objects.create(ticket=self.ticket, title='Submitted', user=self.sale, date=timezone.now())
        self.client.force_login(self.sale)
        response = self.client.get(reverse('admin:lwf_ticket_change', args=[self.ticket.pk]))
        models = [formset.formset.model for formset in response.context['inline_admin_formsets']]
        self.assertIn(FollowUp, models)
