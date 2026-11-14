from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from lwf import notifications
from lwf.models import Notification, Ticket
from lwf.tests.test_workflow import WorkflowTestCase


class NotificationTests(WorkflowTestCase):

    def test_the_receiver_is_notified_and_the_sender_is_not(self):
        self.move(self.submit, self.sale, self.leader)
        note = Notification.objects.get()
        self.assertEqual((note.user, note.kind, note.actor), (self.leader, Notification.ASSIGNED, self.sale))
        self.assertIn(self.ticket.title, note.message)

    def test_reminders_once_per_due_date(self):
        self.move(self.submit, self.sale, self.leader)
        Ticket.objects.filter(pk=self.ticket.pk).update(due_date=timezone.now() - timedelta(hours=1))
        self.assertEqual(notifications.send_due_reminders(), 1)
        self.assertEqual(notifications.send_due_reminders(), 0)
        self.assertTrue(Notification.objects.filter(kind=Notification.OVERDUE, user=self.leader).exists())

    def test_opening_a_notification_marks_it_read(self):
        self.move(self.submit, self.sale, self.leader)
        note = Notification.objects.get()
        self.client.force_login(self.leader)
        response = self.client.get(reverse('admin:lwf_notification_open', args=[note.pk]))
        self.assertRedirects(response, reverse('admin:lwf_ticket_change', args=[self.ticket.pk]),
                             fetch_redirect_response=False)
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)
        self.client.force_login(self.sale)   # someone else's notification
        self.assertEqual(self.client.get(reverse('admin:lwf_notification_open', args=[note.pk])).status_code, 404)
