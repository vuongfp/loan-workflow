from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import translation

from lwf import completeness, workflow
from lwf.models import Action, AttachDocument, FollowUp, LoanDetail, Officer, Ticket
from lwf.tests.factories import complete_application

User = get_user_model()


class WorkflowTestCase(TestCase):

    def setUp(self):
        self.groups = {name: Group.objects.create(name=name) for name in
                       ('SaleTeam', 'SaleManager', 'SaleSupport', 'CEDOfficer', 'Approver', 'CEDAdmin')}
        self.sale = self.user('sale', 'SaleTeam')
        self.leader = self.user('leader', 'SaleManager')
        self.support = self.user('support', 'SaleSupport')
        self.ced1 = self.user('ced1', 'CEDOfficer')
        self.ced2 = self.user('ced2', 'CEDOfficer')
        self.approver1 = self.user('approver1', 'Approver')
        self.approver2 = self.user('approver2', 'Approver')
        self.ced_admin = self.user('cedadmin', 'CEDAdmin')
        self.ticket = Ticket.objects.create(title='AP1', submitter=self.sale,
                                            status=Ticket.OPEN_STATUS)
        LoanDetail.objects.create(ticket=self.ticket, product=3)
        complete_application(self.ticket)
        self.submit = self.action(Ticket.OPEN_STATUS, 'SaleTeam', Ticket.ENDORSE_STATUS, 'SaleManager')
        self.endorse = self.action(Ticket.ENDORSE_STATUS, 'SaleManager', Ticket.SUPPORT_STATUS, 'SaleSupport')
        self.to_ced = self.action(Ticket.SUPPORT_STATUS, 'SaleSupport', Ticket.VERIFY_STATUS, 'CEDOfficer')
        self.recommend = self.action(Ticket.VERIFY_STATUS, 'CEDOfficer', Ticket.APPROVER1_STATUS, 'Approver')
        self.reject = self.action(Ticket.VERIFY_STATUS, 'CEDOfficer', Ticket.REJECT_STATUS, 'SaleTeam')
        self.approve1 = self.action(Ticket.APPROVER1_STATUS, 'Approver', Ticket.APPROVER2_STATUS, 'Approver')
        self.approve2 = self.action(Ticket.APPROVER2_STATUS, 'Approver', Ticket.POST_APPROVAL, 'SaleTeam')

    def user(self, name, group):
        user = User.objects.create_user(name, email='%s@example.com' % name, is_staff=True)
        user.groups.add(Group.objects.get(name=group))
        return user

    def action(self, status, team, next_status, next_team, apprtype=3):
        return Action.objects.create(apprtype=apprtype, status=status, team=self.groups[team],
                                     next_status=next_status, next_team=self.groups[next_team],
                                     description='%s -> %s' % (status, next_status))

    def move(self, action, by, to, **kwargs):
        self.ticket = workflow.transition(self.ticket, action, by, to, comment='ok', **kwargs)
        return self.ticket


class ActionTests(WorkflowTestCase):

    def test_actions_follow_status_and_group(self):
        self.assertEqual(workflow.available_actions(self.sale, self.ticket), [self.submit])
        self.assertEqual(workflow.available_actions(self.leader, self.ticket), [])

    def test_normal_path_is_the_fallback_for_other_approval_types(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(apprtype=1)
        self.ticket.refresh_from_db()
        self.assertEqual(workflow.available_actions(self.sale, self.ticket), [self.submit])

    def test_first_approver_cannot_give_second_approval(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(status=Ticket.APPROVER2_STATUS,
                                                        approver1=self.approver1, assigned_to=self.approver1)
        self.ticket.refresh_from_db()
        self.assertEqual(workflow.available_actions(self.approver1, self.ticket), [])
        self.assertEqual(workflow.available_actions(self.approver2, self.ticket), [])  # no access yet
        Ticket.objects.filter(pk=self.ticket.pk).update(assigned_to=self.approver2)
        self.ticket.refresh_from_db()
        self.assertEqual(workflow.available_actions(self.approver2, self.ticket), [self.approve2])


class AssigneeTests(WorkflowTestCase):

    def test_round_robin_suggests_least_loaded_available_ced(self):
        Officer.objects.create(user=self.ced1, mainteam=self.groups['CEDOfficer'])
        Officer.objects.create(user=self.ced2, mainteam=self.groups['CEDOfficer'])
        Ticket.objects.create(title='BUSY', submitter=self.sale, assigned_to=self.ced1,
                              status=Ticket.VERIFY_STATUS)
        Ticket.objects.create(title='DONE', submitter=self.sale, assigned_to=self.ced2,
                              status=Ticket.COMPLETE_STATUS)
        choice = workflow.assignee_choices(self.to_ced, self.ticket, self.support)
        self.assertEqual(choice.suggested, self.ced2)   # finished work does not count
        self.assertIn(self.ced1, choice.users)

    def test_return_steps_go_to_the_submitter(self):
        choice = workflow.assignee_choices(self.reject, self.ticket, self.ced1)
        self.assertEqual((choice.users, choice.suggested), ([self.sale], self.sale))

    def test_second_approver_excludes_the_first(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(approver1=self.approver1)
        self.ticket.refresh_from_db()
        choice = workflow.assignee_choices(self.approve1, self.ticket, self.approver1)
        self.assertEqual(choice.users, [self.approver2])


class TransitionTests(WorkflowTestCase):

    def walk_to_ced(self):
        self.move(self.submit, self.sale, self.leader)
        self.move(self.endorse, self.leader, self.support)
        return self.move(self.to_ced, self.support, self.ced1)

    def test_walk_fills_roles_numbers_and_history(self):
        with self.captureOnCommitCallbacks(execute=True):
            ticket = self.walk_to_ced()
        self.assertEqual(ticket.status, Ticket.VERIFY_STATUS)
        self.assertEqual((ticket.slead, ticket.ssupport, ticket.ced, ticket.assigned_to),
                         (self.leader, self.support, self.ced1, self.ced1))
        self.assertRegex(ticket.title, r'^DS\.PSL\.\d{2}\.0001$')
        self.assertEqual(FollowUp.objects.filter(ticket=ticket).count(), 3)
        self.assertEqual(mail.outbox[-1].to, ['ced1@example.com'])

    def test_step_not_offered_is_refused(self):
        with self.assertRaises(PermissionDenied):
            self.move(self.endorse, self.sale, self.support)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.OPEN_STATUS)

    def test_assignee_outside_the_list_is_refused(self):
        with self.assertRaises(ValidationError):
            self.move(self.submit, self.sale, self.support)

    def test_reject_by_credit_requires_a_reason(self):
        self.walk_to_ced()
        with self.assertRaises(ValidationError):
            self.move(self.reject, self.ced1, self.sale)
        ticket = self.move(self.reject, self.ced1, self.sale, reject_code=201)
        self.assertEqual((ticket.status, ticket.reject_code), (Ticket.REJECT_STATUS, 201))

    def test_reassign_is_for_team_admins(self):
        self.walk_to_ced()
        with self.assertRaises(PermissionDenied):
            workflow.reassign(self.ticket, self.ced1, self.ced2)
        self.ced_admin.groups.add(self.groups['CEDOfficer'])
        ticket = workflow.reassign(self.ticket, self.ced_admin, self.ced2)
        self.assertEqual((ticket.assigned_to, ticket.ced, ticket.status), (self.ced2, self.ced2, Ticket.VERIFY_STATUS))


class CompletenessTests(WorkflowTestCase):

    def test_sale_cannot_send_an_incomplete_application(self):
        AttachDocument.objects.filter(ticket=self.ticket, related_data=3).delete()
        with translation.override('en'), self.assertRaisesMessage(ValidationError, 'INCOME PROOF'):
            self.move(self.submit, self.sale, self.leader)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.OPEN_STATUS)

    def test_a_deviation_needs_a_reason(self):
        LoanDetail.objects.filter(ticket=self.ticket).update(deviation1=101, deviation1_details='')
        with translation.override('en'):
            self.assertIn('A reason for each deviation chosen', completeness.missing_items(self.ticket))

    def test_complete_application_goes_through(self):
        self.assertEqual(completeness.missing_items(self.ticket), [])
        self.assertEqual(self.move(self.submit, self.sale, self.leader).status, Ticket.ENDORSE_STATUS)
