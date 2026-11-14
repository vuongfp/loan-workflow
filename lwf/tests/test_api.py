import datetime

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from lwf.models import (ApiClient, ApiRequestLog, Applicant, CicSecureLoan, CreditAssessment, Disbursement,
                        LoanContract, LoanDetail, Notification, Ticket)


class ApiTestCase(TestCase):

    def setUp(self):
        self.sale = User.objects.create_user('sale', password='pw-for-tests', is_staff=True)
        self.sale.groups.add(Group.objects.create(name='SaleTeam'))
        self.cra = User.objects.create_user('cra', is_staff=True)
        self.ticket = Ticket.objects.create(title='DS.SS.26.0001', submitter=self.sale, cra=self.cra,
                                            assigned_to=self.cra, status=Ticket.DISBURSEMENT_STATUS)
        self.other = Ticket.objects.create(title='DS.SS.26.0002', status=Ticket.OPEN_STATUS)
        LoanDetail.objects.create(ticket=self.ticket, loanamount=1_000_000_000, loan_tenor=240)
        LoanContract.objects.create(ticket=self.ticket, disbursement_amount=1_000_000_000)
        CreditAssessment.objects.create(ticket=self.ticket)
        self.applicant = Applicant.objects.create(ticket=self.ticket, typeofapplicant=1, name_vn='Trần Thị Bình',
                                                  cid='079190000123', dob=datetime.date(1990, 5, 1))

    def client_with(self, *scopes, ips=''):
        client = ApiClient(name='System %d' % ApiClient.objects.count(), scopes=list(scopes), allowed_ips=ips)
        key = client.new_key()
        client.save()
        return {'HTTP_X_API_KEY': key}

    def get(self, path, headers):
        return self.client.get('/api/v1' + path, **headers)

    def post(self, path, data, headers):
        return self.client.post('/api/v1' + path, data, content_type='application/json', **headers)


class AuthTests(ApiTestCase):

    def test_no_key_bad_key_and_missing_scope(self):
        self.assertEqual(self.get('/applications', {}).status_code, 401)
        self.assertEqual(self.get('/applications', {'HTTP_X_API_KEY': 'lwf_key_nothing.here'}).status_code, 401)
        self.assertEqual(self.get('/applications', self.client_with(ApiClient.REFERENCE_READ)).status_code, 403)

    def test_a_key_works_only_from_its_addresses(self):
        headers = self.client_with(ApiClient.APPLICATIONS_READ, ips='10.0.0.5')
        self.assertEqual(self.get('/applications', headers).status_code, 401)

    def test_personal_data_is_masked_without_the_scope(self):
        masked = self.get('/applications/DS.SS.26.0001', self.client_with(ApiClient.APPLICATIONS_READ)).json()
        self.assertEqual(masked['applicants'][0]['id_number'], '079******123')
        full = self.get('/applications/DS.SS.26.0001',
                        self.client_with(ApiClient.APPLICATIONS_READ, ApiClient.PERSONAL_DATA)).json()
        self.assertEqual(full['applicants'][0]['id_number'], '079190000123')

    def test_an_app_signs_in_and_sees_only_its_applications(self):
        response = self.post('/auth/token', {'username': 'sale', 'password': 'pw-for-tests', 'device': 'phone'}, {})
        self.assertEqual(response.status_code, 200)
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + response.json()['token']}
        numbers = [item['number'] for item in self.get('/applications', headers).json()['items']]
        self.assertEqual(numbers, ['DS.SS.26.0001'])
        self.assertEqual(self.get('/applications/DS.SS.26.0002', headers).status_code, 404)
        self.assertEqual(self.get('/auth/me', headers).json()['username'], 'sale')
        self.assertEqual(self.post('/auth/logout', {}, headers).status_code, 204)
        self.assertEqual(self.get('/auth/me', headers).status_code, 401)

    def test_wrong_password(self):
        self.assertEqual(self.post('/auth/token', {'username': 'sale', 'password': 'no'}, {}).status_code, 401)

    def test_every_call_is_logged(self):
        self.get('/reference/statuses', self.client_with(ApiClient.REFERENCE_READ))
        log = ApiRequestLog.objects.get()
        self.assertEqual((log.path, log.status), ('/api/v1/reference/statuses', 200))
        self.assertIsNotNone(log.client)


class CoreBankingTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.headers = self.client_with(ApiClient.CORE_BANKING)
        self.body = {'application': 'DS.SS.26.0001', 'reference': 'CB-1', 'amount': 600_000_000,
                     'disbursed_at': timezone.now().isoformat(), 'account_number': '1234567890'}

    def test_ready_list(self):
        ready = self.get('/core-banking/ready', self.headers).json()
        self.assertEqual([item['number'] for item in ready], ['DS.SS.26.0001'])

    def test_disbursement_is_recorded_once_and_the_cra_officer_told(self):
        self.assertEqual(self.post('/core-banking/disbursements', self.body, self.headers).status_code, 201)
        again = self.post('/core-banking/disbursements', self.body, self.headers)
        self.assertEqual((again.status_code, again.json()['created']), (200, False))
        self.assertEqual(Disbursement.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.cra, kind=Notification.DISBURSED).exists())

    def test_more_than_the_contract_is_refused(self):
        self.post('/core-banking/disbursements', self.body, self.headers)
        response = self.post('/core-banking/disbursements', {**self.body, 'reference': 'CB-2'}, self.headers)
        self.assertEqual(response.status_code, 422)

    def test_only_at_the_disbursement_step(self):
        response = self.post('/core-banking/disbursements', {**self.body, 'application': 'DS.SS.26.0002'},
                             self.headers)
        self.assertEqual(response.status_code, 409)


class CicAndEkycTests(ApiTestCase):

    def test_a_cic_report_replaces_the_records(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(status=Ticket.VERIFY_STATUS)
        CicSecureLoan.objects.create(applicant=self.applicant, original_amount=1, interest_rate=1, loan_tenor=1,
                                     outstanding_loan=1)
        report = {'id_number': '079190000123', 'report_date': '2026-11-01', 'credit_group': 'G1',
                  'secured_loans': [{'original_amount': 500_000_000, 'interest_rate': 10.5, 'tenor_months': 120,
                                     'outstanding': 300_000_000}]}
        response = self.post('/cic/reports', report, self.client_with(ApiClient.CIC))
        self.assertEqual(response.json(), {'applications_updated': ['DS.SS.26.0001']})
        self.assertEqual(list(CicSecureLoan.objects.values_list('original_amount', flat=True)), [500_000_000])
        self.applicant.refresh_from_db()
        self.assertEqual((self.applicant.cic5Y, self.applicant.total_outstanding), ('G1', 300_000_000))
        self.assertGreater(CreditAssessment.objects.get(ticket=self.ticket).exist_highest_installment, 0)

    def test_ekyc_passes_and_fills_the_id_card_details(self):
        body = {'application': 'DS.SS.26.0001', 'id_number': '079190000123', 'full_name': 'TRAN THI BINH',
                'date_of_birth': '1990-05-01', 'issue_date': '2021-07-01', 'issue_place': 'Cục Cảnh sát QLHC',
                'chip_verified': True, 'face_match_score': 93.5}
        response = self.post('/ekyc/checks', body, self.client_with(ApiClient.EKYC))
        self.assertEqual(response.json()['passed'], True)
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.cra_id_place, 'Cục Cảnh sát QLHC')

    def test_ekyc_reports_differences(self):
        body = {'application': 'DS.SS.26.0001', 'id_number': '079190000123', 'full_name': 'Trần Thị Bích',
                'date_of_birth': '1991-05-01', 'chip_verified': True, 'face_match_score': 95}
        result = self.post('/ekyc/checks', body, self.client_with(ApiClient.EKYC)).json()
        self.assertEqual((result['passed'], result['differences']), (False, ['full_name', 'date_of_birth']))


class AdminIntegrationTests(ApiTestCase):

    def test_demo_cic_lookup_from_the_applicant_page(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(status=Ticket.VERIFY_STATUS, ced=self.sale)
        self.sale.groups.add(Group.objects.get_or_create(name='CEDOfficer')[0])
        self.client.force_login(self.sale)
        response = self.client.get('/admin/lwf/applicant/%d/fetch-cic/' % self.applicant.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.applicant.cic_reports.count(), 1)

    def test_a_new_api_client_gets_a_key_shown_once(self):
        admin = User.objects.create_superuser('root', password='pw-for-tests')
        self.client.force_login(admin)
        response = self.client.post('/admin/lwf/apiclient/add/', {'name': 'Core banking', 'scopes': ['core_banking'],
                                                                   'allowed_ips': '', 'is_active': 'on'}, follow=True)
        message = str(list(response.context['messages'])[0])
        key = message.split('<code style="user-select:all">')[1].split('</code>')[0]
        self.assertEqual(ApiClient.from_key(key).name, 'Core banking')


class CustomerLoansTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        Disbursement.objects.create(ticket=self.ticket, reference='CB-9', amount=400_000_000,
                                    disbursed_at=timezone.now(), account_number='1234567890')
        Applicant.objects.create(ticket=self.other, typeofapplicant=2, name_vn='Trần Thị Bình', cid='079190000123')

    def lookup(self, headers, id_number='079190000123'):
        return self.post('/customers/loans', {'id_number': id_number}, headers)

    def test_every_application_of_the_customer_with_disbursements(self):
        data = self.lookup(self.client_with(ApiClient.APPLICATIONS_READ, ApiClient.PERSONAL_DATA)).json()
        self.assertEqual(data['customer']['id_number'], '079190000123')
        self.assertEqual(sorted(loan['number'] for loan in data['loans']), ['DS.SS.26.0001', 'DS.SS.26.0002'])
        self.assertEqual((data['applications'], data['in_progress'], data['disbursed_total']), (2, 2, 400_000_000))
        loan = next(loan for loan in data['loans'] if loan['number'] == 'DS.SS.26.0001')
        self.assertEqual((loan['stage'], loan['disbursements'][0]['account_number']), ('in_progress', '1234567890'))

    def test_masked_without_the_personal_data_scope(self):
        data = self.lookup(self.client_with(ApiClient.APPLICATIONS_READ)).json()
        self.assertEqual(data['customer']['id_number'], '079******123')
        self.assertIsNone(data['customer']['date_of_birth'])
        loan = next(loan for loan in data['loans'] if loan['disbursements'])
        self.assertEqual(loan['disbursements'][0]['account_number'], '****7890')

    def test_unknown_customer_and_missing_scope(self):
        self.assertEqual(self.lookup(self.client_with(ApiClient.APPLICATIONS_READ), '079000000000').status_code, 404)
        self.assertEqual(self.lookup(self.client_with(ApiClient.REFERENCE_READ)).status_code, 403)

    def test_an_app_sees_only_its_own_applications_of_the_customer(self):
        token = self.post('/auth/token', {'username': 'sale', 'password': 'pw-for-tests'}, {}).json()['token']
        data = self.lookup({'HTTP_AUTHORIZATION': 'Bearer ' + token}).json()
        self.assertEqual([loan['number'] for loan in data['loans']], ['DS.SS.26.0001'])

    def test_the_id_number_stays_out_of_the_log(self):
        self.lookup(self.client_with(ApiClient.APPLICATIONS_READ))
        self.assertEqual(ApiRequestLog.objects.get().path, '/api/v1/customers/loans')


class ApiDemoPageTests(ApiTestCase):

    def test_staff_only_and_demo_customers_listed(self):
        self.assertEqual(self.client.get('/api-demo/').status_code, 302)
        self.client.force_login(self.sale)
        with self.settings(LWF_API_DEMO_SAMPLES=True):
            self.assertContains(self.client.get('/api-demo/'), '079190000123')
        with self.settings(LWF_API_DEMO_SAMPLES=False):
            self.assertNotContains(self.client.get('/api-demo/'), '079190000123')
