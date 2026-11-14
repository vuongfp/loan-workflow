from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from django.utils import translation

from lwf.models import Action, CreditAssessment, FollowUp, ScoreMatrix, ScoreMatrixVersion, ScoreDetail, Ticket
from lwf.tests.factories import complete_application
from lwf.tests.test_admin import RoleTestCase


# The page texts these tests look for are the English ones.
@override_settings(LANGUAGE_CODE='en')
class AdminPageTestCase(RoleTestCase):

    def setUp(self):
        super().setUp()
        self.leader = self.user('leader', 'SaleManager')
        self.submit = Action.objects.create(
            apprtype=3, status=Ticket.OPEN_STATUS, team=Group.objects.get(name='SaleTeam'),
            next_status=Ticket.ENDORSE_STATUS, next_team=Group.objects.get(name='SaleManager'),
            description='Submit to Sale Leader', action_display='Submit to Sale Leader')
        complete_application(self.ticket)

    def url(self, name):
        return reverse('admin:lwf_ticket_%s' % name, args=[self.ticket.pk])


class ChangeStatusPageTests(AdminPageTestCase):

    def test_page_lists_the_steps_of_the_user(self):
        self.client.force_login(self.sale)
        response = self.client.get(self.url('change_status'))
        self.assertContains(response, 'Submit to Sale Leader')
        self.assertContains(response, 'leader')

    def test_submitting_a_step_moves_the_application(self):
        self.client.force_login(self.sale)
        response = self.client.post(self.url('change_status'), {
            'kind': 'action', 'action': self.submit.pk, 'assignee': self.leader.pk, 'comment': 'Ready'})
        self.assertRedirects(response, self.url('change'))
        self.ticket.refresh_from_db()
        self.assertEqual((self.ticket.status, self.ticket.assigned_to), (Ticket.ENDORSE_STATUS, self.leader))
        self.assertTrue(FollowUp.objects.filter(ticket=self.ticket, comment='Ready').exists())

    def test_wrong_assignee_shows_an_error_and_keeps_the_status(self):
        self.client.force_login(self.sale)
        response = self.client.post(self.url('change_status'), {
            'kind': 'action', 'action': self.submit.pk, 'assignee': self.ced.pk}, follow=True)
        self.assertContains(response, 'Choose who receives the application')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.OPEN_STATUS)

    def test_user_without_a_step_cannot_open_the_page(self):
        self.client.force_login(self.ced)
        self.assertNotEqual(self.client.get(self.url('change_status')).status_code, 200)


class ScoringPageTests(AdminPageTestCase):

    def setUp(self):
        super().setUp()
        self.version = ScoreMatrixVersion.objects.create(name='v1', is_active=True)
        ScoreMatrix.objects.create(version=self.version, score_attr='num_CI', description='banks', value_from=0,
                                   value_to=0, value_description='none', adjusted_score=40)
        self.inputs = {'age_borrower_acc': 1, 'conduct_acc': 1, 'where_report': 1,
                       'num_CI': 0, 'no12_Defaults': 0, 'no60_Defaults': 0}

    def test_ced_scores_at_its_step(self):
        self.set_status(Ticket.VERIFY_STATUS)
        self.client.force_login(self.ced)
        response = self.client.post(self.url('credit_scoring'), self.inputs)
        self.assertEqual(response.status_code, 200)
        detail = CreditAssessment.objects.get(ticket=self.ticket)
        self.assertEqual((detail.crr_score, detail.crr_band), ('40.000', 'Band 1'))
        self.assertContains(response, 'Number of Credit Institutions')

    def test_sale_sees_scoring_read_only(self):
        self.client.force_login(self.sale)
        response = self.client.post(self.url('credit_scoring'), self.inputs)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(CreditAssessment.objects.get(ticket=self.ticket).crr_score)


class MemoAndDashboardTests(AdminPageTestCase):

    def test_memo_is_a_pdf_for_users_with_access(self):
        self.client.force_login(self.sale)
        response = self.client.get(self.url('credit_memo'))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_memo_is_refused_without_access(self):
        self.client.force_login(self.other)
        self.assertNotEqual(self.client.get(self.url('credit_memo')).status_code, 200)

    def test_dashboard_shows_my_queue(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(assigned_to=self.sale)
        self.client.force_login(self.sale)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'My work queue')
        self.assertContains(response, 'AP1')
        self.assertNotContains(response, 'Team workload')


class LanguageTests(RoleTestCase):
    def test_the_ui_is_vietnamese_by_default_and_english_on_request(self):
        self.client.force_login(self.sale)
        self.assertContains(self.client.get(reverse('admin:index')), 'Việc của tôi')
        response = self.client.get(reverse('admin:index'), headers={'accept-language': 'en'})
        self.assertContains(response, 'My work queue')


class ReportTests(AdminPageTestCase):

    def test_reports_page_and_excel_export(self):
        self.client.force_login(self.sale)
        response = self.client.get(reverse('admin:lwf_ticket_reports') + '?days=30')
        self.assertContains(response, 'Applications received')
        export = self.client.get(reverse('admin:lwf_ticket_reports_export'))
        self.assertEqual(export.status_code, 200)
        self.assertTrue(export.content.startswith(b'PK'))   # an .xlsx file is a zip archive

    def test_turnaround_counts_the_time_at_each_status(self):
        from datetime import timedelta
        from django.utils import timezone
        from lwf.reports import turnaround_by_status
        start = timezone.now() - timedelta(days=5)
        FollowUp.objects.create(ticket=self.ticket, user=self.sale, title='Submit', date=start + timedelta(days=2),
                                new_status=Ticket.ENDORSE_STATUS)
        Ticket.objects.filter(pk=self.ticket.pk).update(created=start)   # after: saving a follow-up saves the ticket
        with translation.override('en'):
            rows = {row['status']: row['days'] for row in turnaround_by_status(Ticket.objects.all())}
        self.assertEqual(rows['Open'], 2.0)


class ScoreMatrixVersionTests(AdminPageTestCase):

    def setUp(self):
        super().setUp()
        self.version = ScoreMatrixVersion.objects.create(name='v1', is_active=True)
        ScoreMatrix.objects.create(version=self.version, score_attr='num_CI', description='banks', value_from=0,
                                   value_to=0, value_description='none', adjusted_score=40)
        self.inputs = {'age_borrower_acc': 1, 'conduct_acc': 1, 'where_report': 1,
                       'num_CI': 0, 'no12_Defaults': 0, 'no60_Defaults': 0}

    def test_a_score_keeps_the_version_that_made_it(self):
        self.set_status(Ticket.VERIFY_STATUS)
        self.client.force_login(self.ced)
        self.client.post(self.url('credit_scoring'), self.inputs)
        new = self.version.copy('v2')
        new.rows.update(adjusted_score=10)
        new.activate()
        self.assertEqual(ScoreDetail.objects.get(ticket=self.ticket).matrix_version, self.version)
        self.assertTrue(self.version.in_use)
        from lwf import services
        self.assertEqual(services.score_points(self.ticket)['num_CI'], 40)   # still explained by v1
        self.client.post(self.url('credit_scoring'), self.inputs)
        self.assertEqual(ScoreDetail.objects.get(ticket=self.ticket).matrix_version, new)
        self.assertEqual(CreditAssessment.objects.get(ticket=self.ticket).crr_score, '10.000')
