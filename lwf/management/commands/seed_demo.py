import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from lwf import demo
from lwf.models import Action, Ticket


class Command(BaseCommand):
    help = ('Load the reference data and create demo users and synthetic loan applications at every '
            'workflow step. The demo users share the password in DEMO_USER_PASSWORD.')

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=36, help='Number of applications (default 36).')
        parser.add_argument('--reset', action='store_true',
                            help='Delete ALL applications and the demo users first.')
        parser.add_argument('--seed', type=int, default=2026, help='Random seed, for the same data every time.')

    def handle(self, *args, count, reset, seed, **options):
        password = os.environ.get('DEMO_USER_PASSWORD')
        if not password:
            raise CommandError('Set DEMO_USER_PASSWORD (in .env) to the password the demo users should have.')
        if Ticket.objects.exists() and not reset:
            raise CommandError('There are applications already; run with --reset to replace them all.')
        if reset:
            demo.delete_demo_data()
        if not Action.objects.exists():
            call_command('loaddata', 'demo_reference', verbosity=0)
            self.stdout.write('Loaded the reference data.')
        result = demo.seed(password, count=count, random_seed=seed)
        admin_name, admin_password = os.environ.get('DEMO_ADMIN_USERNAME'), os.environ.get('DEMO_ADMIN_PASSWORD')
        if admin_name and admin_password:
            demo.create_superuser(admin_name, admin_password)
        self.stdout.write(self.style.SUCCESS('Created %d users and %d applications.'
                                             % (result.users, result.applications)))
