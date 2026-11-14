from django.core.management.base import BaseCommand

from lwf.notifications import send_due_reminders


class Command(BaseCommand):
    help = 'Notify handlers of applications due within a day or overdue. Run it every hour (cron).'

    def handle(self, *args, **options):
        self.stdout.write('%d reminders created.' % send_due_reminders())
