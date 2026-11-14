import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from lwf import demo
from lwf.models import FollowUp, Ticket


# The demo documents are written to a temporary folder, not the project's media.
@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='lwf-test-media-'))
@mock.patch.dict('os.environ', {'DEMO_USER_PASSWORD': 'demo-test-pass', 'DEMO_ADMIN_USERNAME': ''})
class SeedDemoTests(TestCase):
    def test_every_route_reaches_its_status_through_the_workflow(self):
        call_command('seed_demo', count=len(demo.ROUTES), stdout=mock.MagicMock())
        expected = sorted(route[-1] if route else Ticket.OPEN_STATUS for route in demo.ROUTES)
        self.assertEqual(sorted(Ticket.objects.values_list('status', flat=True)), expected)
        complete = Ticket.objects.filter(status=Ticket.COMPLETE_STATUS).first()
        self.assertTrue(complete.title.startswith('DS.'))
        self.assertNotEqual(complete.approver1_id, complete.approver2_id)
        self.assertGreater(FollowUp.objects.filter(ticket=complete).count(), 5)

    def test_refuses_to_mix_with_existing_applications(self):
        call_command('seed_demo', count=1, stdout=mock.MagicMock())
        with self.assertRaisesMessage(Exception, '--reset'):
            call_command('seed_demo', count=1, stdout=mock.MagicMock())
