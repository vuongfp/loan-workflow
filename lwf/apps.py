from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LoanWorkflowConfig(AppConfig):
    name = 'lwf'
    verbose_name = _('Loan workflow')
