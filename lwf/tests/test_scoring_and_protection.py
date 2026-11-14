from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase

from lwf import scoring
from lwf.models import Applicant, Ticket

User = get_user_model()


def row(attr, value_from, value_to, points):
    return SimpleNamespace(score_attr=attr, value_from=value_from, value_to=value_to,
                           adjusted_score=Decimal(points))


class ScoringTests(SimpleTestCase):

    def test_zero_is_scored(self):
        total, points = scoring.score({'num_CI': 0}, [row('num_CI', 0, 0, 30), row('num_CI', 1, 6, 5)])
        self.assertEqual(points['num_CI'], 30)
        self.assertEqual(total, 30)

    def test_unmatched_field_scores_zero_not_previous_points(self):
        total, points = scoring.score({'age': 30, 'resstat': 9},
                                      [row('age', 25, 40, 20), row('resstat', 1, 3, 10)])
        self.assertEqual(points['resstat'], 0)
        self.assertEqual(total, 20)

    def test_field_without_matrix_rows_scores_zero(self):
        total, _ = scoring.score({'age': 30, 'where_report': 1}, [row('age', 25, 40, 20)])
        self.assertEqual(total, 20)

    def test_missing_value_scores_zero(self):
        total, _ = scoring.score({'age': None}, [row('age', 0, 100, 20)])
        self.assertEqual(total, 0)

    def test_range_bounds_are_inclusive_and_first_match_wins(self):
        rows = [row('dsr', 0, 50, 40), row('dsr', 50, 101, 10)]
        self.assertEqual(scoring.score({'dsr': 50}, rows)[0], 40)
        self.assertEqual(scoring.score({'dsr': 101}, rows)[0], 10)


class AccessTestCase(TestCase):

    def setUp(self):
        self.sale = User.objects.create_user('sale', is_staff=True)
        self.other = User.objects.create_user('other', is_staff=True)
        self.ticket = Ticket.objects.create(title='AP1', submitter=self.sale,
                                            status=Ticket.OPEN_STATUS)
        self.applicant = Applicant.objects.create(ticket=self.ticket, typeofapplicant=1)


class ProtectTests(AccessTestCase):

    def test_deleting_a_user_with_tickets_is_blocked(self):
        with self.assertRaises(ProtectedError):
            self.sale.delete()
        self.assertTrue(Ticket.objects.filter(pk=self.ticket.pk).exists())
