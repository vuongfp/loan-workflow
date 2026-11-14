"""
Django Admin (Unfold theme) as the main UI for loan applications.

Who sees an application follows lwf.access.accessible_tickets; who may edit
which part follows lwf.access.editable_sections (role x status). Django model
permissions are not used for applications: the rules live in lwf.access.
Status changes still go through the workflow screen (link on each application).
"""
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.humanize.templatetags.humanize import intcomma
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.db.models import OuterRef, Subquery
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext, gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter, RangeDateFilter, RelatedDropdownFilter
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.widgets import UnfoldAdminSelectWidget, UnfoldAdminTextInputWidget

from lwf import (completeness, contracts, integrations, memo, notifications, ocr, policy, reports, services,
                 workflow)
from lwf.access import (CED, CRA, SALE, SALE_EDIT_STATUSES, accessible_tickets, can_access_ticket,
                        editable_sections, field_section, is_team_admin, user_in_groups)
from lwf.models import (Action, ApiClient, ApiRequestLog, ApiToken, Applicant, AttachDocument, BusinessIncome,
                        CicCreditCard, CicOverDraft, CicReport, CicSecureLoan, CicUnSecureLoan, CollaManager,
                        CollateralContract, Condition, ContractTemplate, CraDocInfo, CraLoanSaleParty,
                        CreditAssessment, CreditDecision, CreditPolicy, CreditSettings, CustomerType, Disbursement,
                        DocumentExtraction, EkycCheck, FollowUp, HouseholdIncome, LoanContract, LoanDetail,
                        LoanEarlyRepayment, LoanScheme, Location, LOV, Notification, Officer, PanelCar, PanelProject,
                        Product, product_choices, RentalIncome, SalaryIncome, ScoreDetail, ScoreMatrix,
                        ScoreMatrixVersion, subproduct_choices, Ticket)

admin.site.site_header = 'Loan Workflow'
admin.site.index_title = _('Dashboard')
admin.site.site_url = None    # the admin is the whole app: no "Return to site" link
# Home page: lwf.dashboard.dashboard_callback (UNFOLD['DASHBOARD_CALLBACK']) fills it.
admin.site.index_template = 'admin/lwf/dashboard.html'


# ---------------------------------------------------------------- shared helpers

class MoneyInputMixin:
    """VND amounts (BigIntegerField) show and accept thousand separators: 1,500,000."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.BigIntegerField):
            kwargs['widget'] = UnfoldAdminTextInputWidget(attrs={'inputmode': 'numeric'})
            kwargs['localize'] = True
        return super().formfield_for_dbfield(db_field, request, **kwargs)


def model_field_names(model, exclude=()):
    return [f.name for f in model._meta.fields if f.editable and not f.primary_key and f.name not in exclude]


class TicketSectionInline(MoneyInputMixin):
    """Inline on an application; `section` is the part it belongs to (SALE, CED or CRA)."""
    section = SALE
    always_readonly = ()
    tab = True
    extra = 0

    def _ticket(self, obj):
        return obj

    def _can_edit(self, request, obj):
        ticket = self._ticket(obj)
        return ticket is not None and self.section in editable_sections(request.user, ticket)

    def has_view_permission(self, request, obj=None):
        return obj is None or can_access_ticket(request.user, self._ticket(obj))

    def has_change_permission(self, request, obj=None):
        return obj is not None and self._can_edit(request, obj)

    def has_add_permission(self, request, obj=None):
        return obj is not None and self._can_edit(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_add_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.always_readonly)
        if obj is not None and not self._can_edit(request, obj):
            readonly += model_field_names(self.model, exclude=[self.fk_name or 'ticket'])
        return readonly


STATUS_GROUPS = {
    'info': [Ticket.OPEN_STATUS, Ticket.ENDORSE_STATUS, Ticket.SUPPORT_STATUS, Ticket.SD_APPROVE_EXCEPTION,
             Ticket.HS_APPROVE_EXCEPTION],
    'primary': [Ticket.VERIFY_STATUS, Ticket.APPROVER1_STATUS, Ticket.APPROVER2_STATUS, Ticket.CONCUR_STATUS,
                Ticket.VALUATION_STATUS, Ticket.POST_APPROVAL],
    'warning': [Ticket.SS_RQ_UPDATE, Ticket.CED_RQ_UPDATE, Ticket.A1_RQ_UPDATE, Ticket.A2_RQ_UPDATE,
                Ticket.CRA_RQ_UPDATE_STATUS, Ticket.CEDCK_RQ_UPDATE],
    'success': [Ticket.DOCSPREP_STATUS, Ticket.CONFIRMFDISB_STATUS, Ticket.CEDCHEKING_STATUS,
                Ticket.DISBURSEMENT_STATUS, Ticket.COMPLETE_STATUS],
    'danger': [Ticket.REJECT_STATUS, Ticket.CLOSED_STATUS],
}
STATUS_COLOR_BY_CODE = {code: color for color, codes in STATUS_GROUPS.items() for code in codes}
STATUS_LABEL_COLORS = {str(label): color for color, codes in STATUS_GROUPS.items()
                       for code, label in Ticket.STATUS_CHOICES if code in codes}


def vnd(value):
    return '%s VND' % intcomma(value or 0)


# ---------------------------------------------------------------- application inlines

class ScoringForm(forms.ModelForm):
    class Meta:
        model = ScoreDetail
        fields = services.SCORING_INPUTS
        widgets = {name: UnfoldAdminSelectWidget for name in fields}


class LoanAdminForm(forms.ModelForm):
    product = forms.TypedChoiceField(label=_('Product'), coerce=int, required=False, empty_value=None,
                                     choices=lambda: [('', '---------')] + product_choices(),
                                     widget=UnfoldAdminSelectWidget)
    subproduct = forms.TypedChoiceField(label=_('Sub-product'), coerce=int, required=False, empty_value=None,
                                        choices=lambda: [('', '---------')] + subproduct_choices(),
                                        widget=UnfoldAdminSelectWidget)

    class Meta:
        model = LoanDetail
        fields = '__all__'


class OnePerApplicationInline(TicketSectionInline, StackedInline):
    """A record every application has exactly one of."""
    can_delete = False
    max_num = min_num = 1


class LoanInline(OnePerApplicationInline):
    model = LoanDetail
    form = LoanAdminForm
    verbose_name = verbose_name_plural = _('Loan request')
    always_readonly = ('highest_installment', 'lowest_installment', 'average_installment')
    autocomplete_fields = ('loan_pricing_scheme',)
    fieldsets = (
        (None, {'fields': (
            ('product', 'subproduct'), ('loanamount', 'loan_tenor'), ('loanprogram', 'loan_pricing_scheme'),
            ('purpose', 'purposefinacing'), 'purposedetail', 'purpose_details', ('loan_moa', 'loan_subject'),
            'loan_land_value_only', ('deviation1', 'deviation2'), 'deviation1_details', 'deviation2_details',
            'sale_note')}),
        (_('Monthly installments (calculated)'), {'fields': (
            ('highest_installment', 'lowest_installment', 'average_installment'),)}),
    )


class CreditDecisionInline(OnePerApplicationInline):
    model = CreditDecision
    section = CED
    verbose_name = verbose_name_plural = _('Credit decision (CED)')
    fields = (('approved_amount', 'desktop_valuation', 'report_valuation'),
              ('variance', 'covid_affected', 'portfolio_capping'), 'error_codes',
              'recommendation', 'approver1_comment', 'approver2_comment', 'values_report')


class LoanContractInline(OnePerApplicationInline):
    model = LoanContract
    section = CRA
    verbose_name = verbose_name_plural = _('Loan contract (CRA)')
    always_readonly = ('credit_limit_in_words',)
    fields = (('loan_amount', 'credit_limit', 'disbursement_amount'), 'credit_limit_in_words',
              ('interest_rate', 'margin', 'early_repayment_fee'), ('tenor', 'disbursement_method'),
              'purpose', 'conditions')


class ApplicantInline(TicketSectionInline, TabularInline):
    model = Applicant
    fields = ('name_vn', 'cid', 'typeofapplicant', 'dob', 'relationship_bank', 'income_total')
    always_readonly = ('income_total',)
    show_change_link = True

    @display(description=_('Monthly income'))
    def income_total(self, obj):
        return vnd(obj.total)

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        # Only the columns shown here; the full record is on the applicant page.
        return [name for name in readonly if name in self.fields]


class CollateralInline(TicketSectionInline, StackedInline):
    model = CollaManager
    verbose_name, verbose_name_plural = _('Collateral'), _('Collaterals')
    autocomplete_fields = ('project_name', 'car_dealer')
    # The contract data (CRA) is on the collateral's own page.
    show_change_link = True
    fieldsets = (
        (_('Collateral'), {'fields': (
            ('colla_type', 'mortgage_type'), ('existing_collateral', 'title_deed', 'address_available'),
            'spa_or_estimated')}),
        (_('Property'), {'classes': ['collapse'], 'fields': (
            'fulladdress_vn', ('land_plot', 'land_map', 'bedrooms'), ('land_width', 'land_alley_width'),
            ('land_area', 'built_up_area'), ('construction_status', 'occupancy'),
            ('project_name', 'project_dealer', 'project_developer'), ('mefstatus', 'mefexpdt', 'mefavailm'))}),
        (_('Car'), {'classes': ['collapse'], 'fields': (
            ('car_brand', 'car_model', 'car_year'), ('car_group', 'car_class'), 'car_spa_value',
            ('car_dealer', 'car_dealer_other_name'), ('car_efstatus', 'car_efexpdt', 'car_efavailm'))}),
    )


class ConditionInline(TicketSectionInline, TabularInline):
    model = Condition
    section = CED
    fields = ('condition_type', 'condition_detail', 'dox_type', 'followbyced_status', 'followbycra_status')


class DocumentInline(TicketSectionInline, TabularInline):
    model = AttachDocument
    verbose_name, verbose_name_plural = _('Document'), _('Documents')
    fields = ('related_data', 'file', 'filename', 'uploaded_at', 'ai_reading')
    always_readonly = ('uploaded_at', 'ai_reading')

    @display(description=_('AI reading'))
    def ai_reading(self, obj):
        if not obj.pk or not obj.file:
            return '-'
        latest = obj.extractions.first()
        text = _('Read with AI') if latest is None else (_('Applied') if latest.applied_at else _('Review'))
        return format_html('<a class="text-primary-600 underline" href="{}">{}</a>',
                           reverse('admin:lwf_ticket_document_reading', args=[obj.ticket_id, obj.pk]), text)

    def _can_edit(self, request, obj):
        # Sale uploads application documents, CED valuation documents.
        return bool(editable_sections(request.user, self._ticket(obj)) & {SALE, CED})


class CraDocumentInline(TicketSectionInline, TabularInline):
    model = CraDocInfo
    section = CRA
    verbose_name, verbose_name_plural = _('Contract document'), _('Contract documents')
    fields = ('contract_type', 'contract_number', 'sign_date', 'signer', 'position', 'saler1', 'saler2',
              'print_link')
    always_readonly = ('print_link',)

    @display(description=_('Print'))
    def print_link(self, obj):
        if not obj.pk:
            return '-'
        return format_html('<a class="text-primary-600 underline" href="{}">{}</a> &middot; '
                           '<a class="text-primary-600 underline" href="{}" target="_blank">{}</a>',
                           reverse('admin:lwf_ticket_contract_docx', args=[obj.ticket_id, obj.pk]), _('Word contract'),
                           reverse('admin:lwf_ticket_contract', args=[obj.ticket_id, obj.pk]), _('Parties (PDF)'))


class CraSalePartyInline(TicketSectionInline, TabularInline):
    model = CraLoanSaleParty
    section = CRA
    verbose_name, verbose_name_plural = _('Sale party'), _('Sale parties')
    fields = ('cra_salepart_name', 'cra_salepart_year', 'cra_salepart_id', 'cra_salepart_idplace',
              'cra_salepart_peraddress')


class FollowUpInline(TabularInline):
    model = FollowUp
    verbose_name, verbose_name_plural = _('Workflow step'), _('Workflow history')
    fields = ('date', 'by', 'title', 'new_status', 'comment')
    readonly_fields = fields
    show_title = False
    ordering = ('-date',)
    tab = True
    extra = 0
    can_delete = False

    @display(description=_('By'))
    def by(self, obj):
        return (obj.user.get_full_name() or obj.user.username) if obj.user_id else '-'

    def has_view_permission(self, request, obj=None):
        # Everyone who may open the application sees its history.
        return obj is None or can_access_ticket(request.user, obj)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------- applications

@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = ('title', 'primary_applicant', 'product_name', 'loan_amount', 'status_badge',
                    'handler', 'due', 'modified')
    list_display_links = ('title', 'primary_applicant')
    list_select_related = ('loan', 'assigned_to')
    list_filter = (('status', ChoicesDropdownFilter), ('apprtype', ChoicesDropdownFilter),
                   ('assigned_to', RelatedDropdownFilter), ('created', RangeDateFilter))
    list_filter_submit = True
    search_fields = ('title', 'applicant__name_vn', 'applicant__name_en', 'applicant__cid')
    search_help_text = _('Application number, applicant name or ID number')
    ordering = ('-modified',)
    list_per_page = 50
    inlines = (LoanInline, ApplicantInline, CollateralInline, CreditDecisionInline, ConditionInline,
               DocumentInline, LoanContractInline, CraDocumentInline, CraSalePartyInline, FollowUpInline)
    fieldsets = (
        (_('Overview'), {'classes': ['tab'], 'fields': (
            ('title', 'status_chip', 'handler', 'due'), ('primary_applicant_link', 'loan_summary'),
            'checklist', 'policy_check', ('apprtype', 'created', 'modified'), 'description')}),
        (_('People'), {'classes': ['tab'], 'fields': (
            ('submitter', 'assigned_to'), ('slead', 'ssupport'), ('sdirector', 'pfshead'),
            ('ced', 'cra'), ('approver1', 'approver2'))}),
        (_('Credit assessment'), {'classes': ['tab'], 'fields': (
            ('monthly_income', 'existing_installments', 'living_cost'), ('dsr', 'net_surplus'),
            ('segment', 'crr_score'))}),
    )
    computed_fields = ('status_badge', 'status_chip', 'checklist', 'policy_check', 'handler', 'due',
                       'primary_applicant_link', 'loan_summary', 'monthly_income', 'existing_installments',
                       'living_cost', 'dsr', 'net_surplus', 'segment', 'crr_score')
    # Changed only by the workflow, never typed in.
    workflow_fields = ('title', 'created', 'modified', 'submitter', 'assigned_to', 'slead', 'ssupport',
                       'sdirector', 'pfshead', 'ced', 'cra', 'approver1', 'approver2', 'due_date')

    def get_queryset(self, request):
        primary = Applicant.objects.filter(ticket=OuterRef('pk'), typeofapplicant=1)
        product = Product.objects.filter(product_code=OuterRef('loan__product')).order_by('id')
        queryset = super().get_queryset(request).annotate(
            primary_name=Subquery(primary.values('name_vn')[:1]),
            product_label=Subquery(product.values('product')[:1]))
        return accessible_tickets(request.user, queryset)

    # ------------------------------------------------------------ permissions

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff and (obj is None or can_access_ticket(request.user, obj))

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        return bool(editable_sections(request.user, obj))

    def has_add_permission(self, request):
        return request.user.is_superuser or user_in_groups(request.user, 'SaleTeam')

    def has_delete_permission(self, request, obj=None):
        # Applications are cancelled through the workflow, never deleted.
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.computed_fields) + list(self.workflow_fields)
        sections = editable_sections(request.user, obj) if obj else set()
        if CED not in sections:
            readonly.append('apprtype')
        if SALE not in sections:
            readonly.append('description')
        return readonly

    # ------------------------------------------------------------ add and save

    def add_view(self, request, form_url='', extra_context=None):
        """Create a draft application (with its empty loan and collateral) on confirmation."""
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == 'POST':
            ticket = services.create_application(request.user)
            self.message_user(request, _('Application %s created.') % ticket.title)
            return redirect('admin:lwf_ticket_change', ticket.pk)
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta,
                   'title': _('New loan application')}
        return TemplateResponse(request, 'admin/lwf/ticket/confirm_create.html', context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = {**(extra_context or {}), 'show_save_and_add_another': False}
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_formset(self, request, form, formset, change):
        if formset.model is Applicant:
            for applicant_form in formset.forms:
                if applicant_form.has_changed() and not applicant_form.cleaned_data.get('DELETE'):
                    services.normalize_applicant(applicant_form.instance)
        super().save_formset(request, form, formset, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        ticket = form.instance
        services.apply_loan_change(LoanDetail.objects.get(ticket=ticket))
        services.recalc_credit_summary(ticket)

    # ------------------------------------------------------------ columns and fields

    # ------------------------------------------------------------ workflow, scoring and memo pages

    actions_detail = ('change_status', 'credit_scoring', 'credit_memo')

    def _ticket_for(self, request, object_id):
        return get_object_or_404(accessible_tickets(request.user), pk=object_id)

    def _page(self, request, ticket, template, title, **context):
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta, 'original': ticket,
                   'title': title, 'change_url': reverse('admin:lwf_ticket_change', args=[ticket.pk]), **context}
        return TemplateResponse(request, template, context)

    def has_workflow_permission(self, request, object_id=None):
        ticket = accessible_tickets(request.user).filter(pk=object_id).first()
        return bool(ticket) and bool(workflow.available_actions(request.user, ticket)
                                     or request.user.is_superuser or is_team_admin(request.user, ticket))

    def has_view_details_permission(self, request, object_id=None):
        return accessible_tickets(request.user).filter(pk=object_id).exists()

    @action(description=_('Change status'), url_path='change-status', permissions=['workflow'],
            icon='move_down')
    def change_status(self, request, object_id):
        """The steps the user can take now, one card each, plus re-assign for team admins."""
        ticket = self._ticket_for(request, object_id)
        user = request.user
        if request.method == 'POST':
            try:
                assignee = User.objects.get(pk=request.POST.get('assignee') or 0)
                comment = request.POST.get('comment', '').strip()
                if request.POST.get('kind') == 'reassign':
                    ticket = workflow.reassign(ticket, user, assignee, comment)
                else:
                    step = get_object_or_404(Action, pk=request.POST.get('action'))
                    codes = {name: int(request.POST[name]) for name in ('reject_code', 'qc_code')
                             if request.POST.get(name, '').isdigit()}
                    ticket = workflow.transition(ticket, step, user, assignee, comment, **codes)
                self.message_user(request, _('%(title)s is now "%(status)s", with %(user)s.') % {
                    'title': ticket.title, 'status': ticket.get_status_display(),
                    'user': assignee.get_full_name() or assignee}, messages.SUCCESS)
                return redirect('admin:lwf_ticket_change', ticket.pk)
            except User.DoesNotExist:
                self.message_user(request, _('Choose who receives the application.'), messages.ERROR)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, ' '.join(getattr(error, 'messages', [str(error)])), messages.ERROR)
            ticket.refresh_from_db()
        steps = [{'action': step, 'kind': workflow.step_kind(step),
                  'label': gettext(step.action_display or step.description),
                  'choice': workflow.assignee_choices(step, ticket, user),
                  'reject': workflow.needs_reject_code(step, user), 'qc': workflow.needs_qc_code(step, user)}
                 for step in workflow.available_actions(user, ticket)]
        steps.sort(key=lambda step: workflow.STEP_KINDS.index(step['kind']))
        reassign_users = (workflow.reassign_choices(ticket)
                          if user.is_superuser or is_team_admin(user, ticket) else [])
        return self._page(request, ticket, 'admin/lwf/ticket/change_status.html', _('Change status'),
                          steps=steps, reassign_users=reassign_users, reject_codes=LOV.REJECT_CHOICES,
                          qc_codes=LOV.QC_CHOICES, summary=self._summary(ticket),
                          checks=completeness.checks(ticket) if ticket.status in SALE_EDIT_STATUSES else None,
                          incomplete=ticket.status in SALE_EDIT_STATUSES and bool(completeness.missing_items(ticket)),
                          disabled_attrs={'disabled': True})

    def _summary(self, ticket):
        """What a handler needs to see before deciding, at the top of the workflow page."""
        detail = self._detail(ticket)
        return [(_('Primary applicant'), self.primary_applicant_link(ticket)),
                (_('Loan'), self.loan_summary(ticket)),
                (_('Monthly income'), vnd(detail.monthly_income) if detail else '-'),
                (_('DSR highest / average'), self.dsr(ticket)),
                (_('CRR score'), self.crr_score(ticket)),
                (_('Credit policy'), self.policy_check(ticket)),
                (_('Due'), self.due(ticket))]

    @action(description=_('CRR scoring'), url_path='crr-scoring', permissions=['view_details'],
            icon='leaderboard')
    def credit_scoring(self, request, object_id):
        """Bureau inputs (CED), the score, its band and the points of each criterion."""
        ticket = self._ticket_for(request, object_id)
        can_score = CED in editable_sections(request.user, ticket)
        detail = CreditAssessment.objects.get_or_create(ticket=ticket)[0]
        form = ScoringForm(request.POST or None,
                           instance=ScoreDetail.objects.filter(ticket=ticket).first() or ScoreDetail(ticket=ticket))
        if not can_score:
            for field in form.fields.values():
                field.disabled = True
        points = None
        if request.method == 'POST' and can_score and form.is_valid():
            score, band, points = services.score_application(ticket, form.cleaned_data)
            self.message_user(request, _('CRR score %(score)s, %(band)s.') % {'score': score, 'band': band},
                              messages.SUCCESS)
            detail.refresh_from_db()
        elif form.instance.pk:
            points = services.score_points(ticket)
        return self._page(request, ticket, 'admin/lwf/ticket/credit_scoring.html', _('CRR scoring'),
                          form=form, can_score=can_score, detail=detail,
                          version=form.instance.matrix_version if form.instance.pk else ScoreMatrixVersion.active(),
                          points=[(ScoreDetail._meta.get_field(name).verbose_name, value)
                                  for name, value in points.items()] if points else None)

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path('reports/', view(self.reports_view), name='lwf_ticket_reports'),
            path('reports/export/', view(self.reports_export), name='lwf_ticket_reports_export'),
            path('<path:object_id>/documents/<int:doc_id>/reading/', view(self.document_reading),
                 name='lwf_ticket_document_reading'),
            path('<path:object_id>/contract/<int:doc_id>/docx/', view(self.contract_docx),
                 name='lwf_ticket_contract_docx'),
            path('<path:object_id>/contract/<int:doc_id>/', view(self.contract_pdf), name='lwf_ticket_contract'),
        ] + super().get_urls()

    def _report_days(self, request):
        days = request.GET.get('days', '')
        return int(days) if days.isdigit() and int(days) in reports.PERIODS else 90

    def reports_view(self, request):
        """Volumes, turnaround per step and rejection reasons over the applications the user may see."""
        data = reports.report(request.user, self._report_days(request))
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta, 'title': _('Reports'),
                   'data': data, 'charts': reports.charts(data),
                   'periods': [{'days': days, 'url': '?days=%d' % days, 'active': days == data['days']}
                               for days in reports.PERIODS],
                   'export_url': '%s?days=%d' % (reverse('admin:lwf_ticket_reports_export'), data['days'])}
        return TemplateResponse(request, 'admin/lwf/reports.html', context)

    def reports_export(self, request):
        data = reports.report(request.user, self._report_days(request))
        response = HttpResponse(reports.excel(data), content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
        response['Content-Disposition'] = 'attachment; filename="loan-report-%s.xlsx"' % (
            data['now'].strftime('%Y%m%d'))
        return response

    def document_reading(self, request, object_id, doc_id):
        """AI reading of one document: run it, compare with the application, fill the empty fields."""
        ticket = self._ticket_for(request, object_id)
        document = get_object_or_404(AttachDocument, pk=doc_id, ticket=ticket)
        can_edit = bool(editable_sections(request.user, ticket))
        if request.method == 'POST':
            if not can_edit:
                raise PermissionDenied
            if request.POST.get('do') == 'apply':
                extraction = get_object_or_404(DocumentExtraction, pk=request.POST.get('extraction'),
                                               document=document)
                filled = ocr.apply(extraction)
                self.message_user(request, _('%d field(s) filled from the document.') % filled, messages.SUCCESS)
            else:
                kind = request.POST.get('kind')
                if kind not in ocr.KINDS:
                    raise PermissionDenied
                extraction = ocr.read(document, kind, request.user)
                if extraction.error:
                    self.message_user(request, extraction.error, messages.ERROR)
            return redirect('admin:lwf_ticket_document_reading', ticket.pk, document.pk)
        extraction = document.extractions.filter(error='').first()
        return self._page(request, ticket, 'admin/lwf/ticket/document_reading.html', _('AI reading'),
                          document=document, extraction=extraction, can_edit=can_edit, enabled=ocr.enabled(),
                          kinds=[(key, label) for key, (label, _schema) in ocr.KINDS.items()],
                          default_kind=ocr.default_kind(document),
                          rows=ocr.comparison(extraction) if extraction else [],
                          last_error=document.extractions.exclude(error='').first())

    def contract_docx(self, request, object_id, doc_id):
        """The full contract as a Word file, from the active template of its type."""
        ticket = self._ticket_for(request, object_id)
        doc = get_object_or_404(CraDocInfo, pk=doc_id, ticket=ticket)
        response = HttpResponse(contracts.contract_docx(doc), content_type=(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
        response['Content-Disposition'] = 'attachment; filename="%s-%s.docx"' % (
            ticket.title, doc.contract_number or doc.pk)
        return response

    def contract_pdf(self, request, object_id, doc_id):
        ticket = self._ticket_for(request, object_id)
        doc = get_object_or_404(CraDocInfo, pk=doc_id, ticket=ticket)
        response = HttpResponse(memo.credit_contract_pdf(doc), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="contract-%s.pdf"' % (doc.contract_number or doc.pk)
        return response

    @action(description=_('Credit memo (PDF)'), url_path='credit-memo', permissions=['view_details'],
            icon='picture_as_pdf')
    def credit_memo(self, request, object_id):
        ticket = self._ticket_for(request, object_id)
        response = HttpResponse(memo.credit_memo_pdf(ticket), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="credit-memo-%s.pdf"' % ticket.title
        return response

    @display(description=_('Primary applicant'), ordering='primary_name')
    def primary_applicant(self, obj):
        return getattr(obj, 'primary_name', None) or '-'

    @display(description=_('Product'))
    def product_name(self, obj):
        return getattr(obj, 'product_label', None) or '-'

    @display(description=_('Loan amount'), ordering='loan__loanamount')
    def loan_amount(self, obj):
        loan = getattr(obj, 'loan', None)
        return intcomma(loan.loanamount) if loan else '-'

    @display(description=_('Status'), ordering='status', label=STATUS_LABEL_COLORS)
    def status_badge(self, obj):
        return obj.get_status_display()

    @display(description=_('Status'))
    def status_chip(self, obj):
        color = STATUS_COLOR_BY_CODE.get(obj.status, 'info')
        return format_html('<span class="lwf-chip lwf-chip-{}">{}</span>', color, obj.get_status_display())

    @display(description=_('Credit policy'))
    def policy_check(self, obj):
        """Limits of the product the application is outside of, and the deviation codes to declare."""
        if not obj.pk:
            return '-'
        found = policy.breaches(obj)
        if not found:
            return format_html('<span class="lwf-chip lwf-chip-success">{}</span>', _('Within policy'))
        rows = format_html_join('', '<li>{}: {} ({} {}) &rarr; {}</li>', (
            (b.rule, b.actual, _('limit'), b.limit, b.deviation_label) for b in found))
        suggested = policy.suggested_deviations(obj)
        note = format_html('<p class="lwf-policy-note">{} {}</p>', _('Deviation codes still to declare:'),
                           ', '.join(str(code) for code in suggested)) if suggested else ''
        return format_html('<span class="lwf-chip lwf-chip-warning">{}</span><ul class="lwf-missing">{}</ul>{}',
                           _('%d policy limit(s) exceeded') % len(found), rows, note)

    @display(description=_('Ready to send'))
    def checklist(self, obj):
        """What is still missing before Sale can send the application on."""
        if not obj.pk:
            return '-'
        missing = completeness.missing_items(obj)
        if not missing:
            return format_html('<span class="lwf-chip lwf-chip-success">{}</span>', _('Nothing missing'))
        items = format_html_join('', '<li>{}</li>', ((item,) for item in missing))
        return format_html('<span class="lwf-chip lwf-chip-warning">{}</span><ul class="lwf-missing">{}</ul>',
                           _('%d item(s) missing') % len(missing), items)

    @display(description=_('With'), ordering='assigned_to__first_name')
    def handler(self, obj):
        user = obj.assigned_to
        return (user.get_full_name() or user.username) if user else '-'

    @display(description=_('Due'), ordering='due_date')
    def due(self, obj):
        if not obj.due_date:
            return '-'
        text = timezone.localtime(obj.due_date).strftime('%d/%m/%Y')
        if obj.due_date < timezone.now() and obj.status not in workflow.FINISHED_STATUSES:
            return format_html('<span class="lwf-overdue" title="{}">{}</span>', _('Overdue'), text)
        return text

    @display(description=_('Primary applicant'))
    def primary_applicant_link(self, obj):
        applicant = Applicant.objects.filter(ticket=obj, typeofapplicant=1).first() if obj.pk else None
        if not applicant:
            return '-'
        return format_html('<a class="text-primary-600 underline" href="{}">{}</a> &middot; {}',
                           reverse('admin:lwf_applicant_change', args=[applicant.pk]), applicant.name_vn,
                           applicant.cid)

    @display(description=_('Loan'))
    def loan_summary(self, obj):
        loan = LoanDetail.objects.filter(ticket=obj).first() if obj.pk else None
        if not loan or not loan.loanamount:
            return '-'
        return '%s · %s · %s %s' % (loan.get_product_display() or '-', vnd(loan.loanamount), loan.loan_tenor,
                                     _('months'))

    def _detail(self, obj):
        if not hasattr(obj, '_credit_detail'):
            obj._credit_detail = CreditAssessment.objects.filter(ticket=obj).first()
        return obj._credit_detail

    @display(description=_('Monthly income'))
    def monthly_income(self, obj):
        detail = self._detail(obj)
        return vnd(detail.monthly_income) if detail else '-'

    @display(description=_('Existing debt payments (highest)'))
    def existing_installments(self, obj):
        detail = self._detail(obj)
        return vnd(detail.exist_highest_installment) if detail else '-'

    @display(description=_('Living cost'))
    def living_cost(self, obj):
        detail = self._detail(obj)
        return vnd(detail.expenditure) if detail else '-'

    @display(description=_('DSR highest / average'))
    def dsr(self, obj):
        detail = self._detail(obj)
        return '%s%% / %s%%' % (detail.dsr_high, detail.dsr_avg) if detail else '-'

    @display(description=_('Net surplus after payments'))
    def net_surplus(self, obj):
        detail = self._detail(obj)
        return vnd(detail.nst) if detail else '-'

    @display(description=_('Segment'))
    def segment(self, obj):
        detail = self._detail(obj)
        return detail.segmentation if detail else '-'

    @display(description=_('CRR score'))
    def crr_score(self, obj):
        detail = self._detail(obj)
        if not detail or not detail.crr_score:
            return _('Not scored yet')
        return '%s (%s)' % (detail.crr_score, detail.crr_band)


# ---------------------------------------------------------------- applicants

class ApplicantRecordInline(TicketSectionInline):
    """Income and credit-bureau records of one applicant (Sale data)."""
    fk_name = 'applicant'

    def _ticket(self, obj):
        return obj.ticket if obj is not None else None


class SalaryInline(ApplicantRecordInline, StackedInline):
    model = SalaryIncome
    verbose_name, verbose_name_plural = _('Salary'), _('Salaries')
    always_readonly = ('fix_avg', 'var_avg', 'avg')
    fieldsets = (
        (None, {'fields': (('employer', 'designation'), ('contract_type', 'contract_date', 'contract_expdate'),
                           ('length_in_service', 'payment_type'),
                           ('previous_employer', 'previous_length_in_service'))}),
        (_('Fixed pay by month (VND); months counted'), {'fields': (
            'monthamt', ('fix_m1', 'fix_m2', 'fix_m3', 'fix_m4', 'fix_m5', 'fix_m6'),
            ('fix_m7', 'fix_m8', 'fix_m9', 'fix_m10', 'fix_m11', 'fix_m12'))}),
        (_('Variable pay by month (VND); months counted'), {'classes': ['collapse'], 'fields': (
            'varmonthamt', ('var_m1', 'var_m2', 'var_m3', 'var_m4', 'var_m5', 'var_m6'),
            ('var_m7', 'var_m8', 'var_m9', 'var_m10', 'var_m11', 'var_m12'))}),
        (_('Monthly averages (calculated)'), {'fields': (('fix_avg', 'var_avg', 'avg'),)}),
    )


class BusinessInline(ApplicantRecordInline, StackedInline):
    model = BusinessIncome
    verbose_name, verbose_name_plural = _('Business'), _('Businesses')
    always_readonly = ('year1_tangible_net_worth', 'year2_tangible_net_worth', 'year3_tangible_net_worth',
                       'vat_monthly', 'bank_statement_monthly', 'year3_net_sales_turnover', 'monthly_average',
                       'netincome')
    fieldsets = (
        (None, {'fields': (('name', 'shareportion'), ('reg_no', 'reg_dt', 'years'), ('char_capital', 'contributed'),
                           'reg_address', 'ops_address', 'scope', ('industry', 'industrydetail', 'EBITDAmargin'),
                           ('typical_buyers', 'typical_suppliers'))}),
        (_('Financial statements'), {'classes': ['collapse'], 'fields': (
            ('y1', 'y2', 'y3'),
            ('year1_sales_turnover', 'year2_sales_turnover', 'year3_sales_turnover'),
            ('year1_net_profit', 'year2_net_profit', 'year3_net_profit'),
            ('year1_paidup_capital', 'year2_paidup_capital', 'year3_paidup_capital'),
            ('year1_retained_earning', 'year2_retained_earning', 'year3_retained_earning'),
            ('year1_intangible_assets', 'year2_intangible_assets', 'year3_intangible_assets'),
            ('year1_tangible_net_worth', 'year2_tangible_net_worth', 'year3_tangible_net_worth'))}),
        (_('Turnover evidence'), {'fields': (
            ('vat_period', 'vat_amount', 'bank_statement_amount'),
            ('vat_monthly', 'bank_statement_monthly', 'year3_net_sales_turnover'),
            ('monthly_average', 'netincome'))}),
    )


class HouseholdInline(ApplicantRecordInline, StackedInline):
    model = HouseholdIncome
    verbose_name, verbose_name_plural = _('Household business'), _('Household businesses')
    always_readonly = ('monthly_average', 'netincome')
    fieldsets = (
        (None, {'fields': (('name', 'shareportion'), ('reg_no', 'reg_dt', 'years'), ('char_capital', 'contributed'),
                           ('reg_address', 'years_at_address'), 'scope', ('industry', 'margin'),
                           ('typical_buyers', 'typical_suppliers'))}),
        (_('Monthly revenue (VND); months counted'), {'fields': (
            'mamt', ('m1', 'm2', 'm3'), ('m4', 'm5', 'm6'), ('monthly_average', 'netincome'))}),
    )


class RentalInline(ApplicantRecordInline, TabularInline):
    model = RentalIncome
    fields = ('address', 'leasing_price', 'contract_type', 'proxy_margin', 'payment_type', 'mortgage_status',
              'net_income')
    always_readonly = ('net_income',)


class SecuredLoanInline(ApplicantRecordInline, TabularInline):
    model = CicSecureLoan
    verbose_name, verbose_name_plural = _('Secured loan (CIC)'), _('Secured loans (CIC)')
    fields = ('original_amount', 'interest_rate', 'loan_tenor', 'outstanding_loan', 'progressive_disbursement',
              'highest_installment', 'averageinstallment')
    always_readonly = ('highest_installment', 'averageinstallment')


class UnsecuredLoanInline(ApplicantRecordInline, TabularInline):
    model = CicUnSecureLoan
    verbose_name, verbose_name_plural = _('Unsecured loan (CIC)'), _('Unsecured loans (CIC)')
    fields = ('m1', 'm2', 'm3', 'installment')
    always_readonly = ('installment',)


class OverdraftInline(ApplicantRecordInline, TabularInline):
    model = CicOverDraft
    verbose_name, verbose_name_plural = _('Overdraft (CIC)'), _('Overdrafts (CIC)')
    fields = ('interest_rate', 'outstanding_loan', 'installment')
    always_readonly = ('installment',)


class CreditCardInline(ApplicantRecordInline, TabularInline):
    model = CicCreditCard
    verbose_name, verbose_name_plural = _('Credit card (CIC)'), _('Credit cards (CIC)')
    fields = ('bm1', 'bm2', 'bm3', 'bm4', 'bm5', 'bm6', 'avg_balance_6m', 'highest_installment')
    always_readonly = ('avg_balance_6m', 'highest_installment')


class ReceivedRecordInline(ApplicantRecordInline, TabularInline):
    """What other systems sent about the applicant: read-only."""
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.fields


class CicReportInline(ReceivedRecordInline):
    model = CicReport
    fields = ('report_date', 'credit_group', 'source', 'created')


class EkycCheckInline(ReceivedRecordInline):
    model = EkycCheck
    fields = ('created', 'passed', 'chip_verified', 'face_match_score', 'mismatches', 'source')


@admin.register(Applicant)
class ApplicantAdmin(MoneyInputMixin, ModelAdmin):
    list_display = ('name_vn', 'cid', 'typeofapplicant', 'application', 'total_income')
    list_select_related = ('ticket',)
    search_fields = ('name_vn', 'name_en', 'cid', 'ticket__title')
    inlines = (SalaryInline, BusinessInline, HouseholdInline, RentalInline,
               SecuredLoanInline, UnsecuredLoanInline, OverdraftInline, CreditCardInline,
               CicReportInline, EkycCheckInline)
    actions_detail = ('fetch_cic',)
    summary_fields = ('fix', 'var', 'net', 'business', 'household', 'rental', 'total',
                      'highest_installment', 'average_installment')
    fieldsets = (
        (_('Applicant'), {'classes': ['tab'], 'fields': (
            'application', ('name_vn', 'typeofapplicant'), ('cid', 'old_cid', 'nationality'),
            ('dob', 'age', 'gender'), ('marital', 'edulvl'),
            ('permanent_address_vn', 'temporary_address_vn'), ('typehouse', 'resstat', 'reslocation'),
            ('relationship_bank', 'relatedparty'), 'relatedparty_details', 'description')}),
        (_('Credit bureau'), {'classes': ['tab'], 'fields': (
            ('cicdate', 'cic5Y'), ('total_outstanding', 'creditcard'))}),
        (_('Income summary (calculated)'), {'classes': ['tab'], 'fields': (
            ('fix', 'var', 'net'), ('business', 'household', 'rental'), 'total',
            ('highest_installment', 'average_installment'))}),
        (_('Contract data (CRA)'), {'classes': ['tab'], 'fields': (
            ('cra_id_place', 'cra_id_date'), 'cra_permanent_address', 'cra_temporary_address')}),
    )

    def get_queryset(self, request):
        tickets = accessible_tickets(request.user)
        return super().get_queryset(request).filter(ticket__in=tickets)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff and (obj is None or (obj.ticket and can_access_ticket(request.user, obj.ticket)))

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        return bool(obj.ticket and editable_sections(request.user, obj.ticket) & {SALE, CRA})

    def has_add_permission(self, request):
        # Applicants are added on their application.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = ['application', 'age'] + list(self.summary_fields)
        sections = editable_sections(request.user, obj.ticket) if obj and obj.ticket else set()
        editable_names = model_field_names(Applicant, exclude=['ticket'])
        return readonly + [name for name in editable_names
                           if field_section(name) not in sections and name not in readonly]

    @action(description=_('Look up CIC (demo)'), url_path='fetch-cic', icon='travel_explore',
            permissions=['fetch_cic'])
    def fetch_cic(self, request, object_id):
        """The demo stands in for the CIC connection: a made-up but stable report for the ID number."""
        applicant = get_object_or_404(self.get_queryset(request), pk=object_id)
        integrations.apply_cic_report(applicant, integrations.demo_cic_report(applicant.cid), source='demo')
        self.message_user(request, _('CIC report received and applied; the credit summary is recalculated.'),
                          messages.SUCCESS)
        return redirect('admin:lwf_applicant_change', applicant.pk)

    def has_fetch_cic_permission(self, request, object_id=None):
        applicant = Applicant.objects.filter(pk=object_id).select_related('ticket').first()
        return bool(applicant and applicant.ticket and editable_sections(request.user, applicant.ticket) & {SALE, CED})

    def save_model(self, request, obj, form, change):
        services.normalize_applicant(obj)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.ticket:
            services.recalc_credit_summary(form.instance.ticket)

    @display(description=_('Application'))
    def application(self, obj):
        if not obj.ticket_id:
            return '-'
        return format_html('<a class="text-primary-600 underline" href="{}">{}</a>',
                           reverse('admin:lwf_ticket_change', args=[obj.ticket_id]), obj.ticket.title)

    @display(description=_('Monthly income'), ordering='total')
    def total_income(self, obj):
        return vnd(obj.total)


# ---------------------------------------------------------------- collaterals

class CollateralContractInline(TicketSectionInline, StackedInline):
    model = CollateralContract
    section = CRA
    fk_name = 'collateral'
    tab = False
    can_delete = False
    max_num = 1
    extra = 1
    verbose_name = verbose_name_plural = _('Contract data (CRA)')
    always_readonly = ('car_spa_value_inwords', 'area_inwords', 'house_using_area_inwords')
    fieldsets = (
        (_('Car'), {'classes': ['collapse'], 'fields': (
            ('car_brand', 'car_body_no', 'car_machine_no'), ('car_dealer', 'car_spa_value'),
            'car_spa_value_inwords')}),
        (_('Land and house'), {'fields': (
            ('land_plot', 'land_map'), ('land_area', 'built_up_area'), 'fulladdress',
            ('land_using_type', 'land_using_purpose'), ('land_using_time', 'land_using_source'),
            ('house_structure', 'house_level'), ('house_numfloor', 'house_built_year', 'house_using_time'),
            ('house_built_up_area', 'house_using_area'), 'area_inwords', 'house_using_area_inwords',
            ('floor_area', 'area'))}),
        (_('Apartment purchase'), {'classes': ['collapse'], 'fields': (
            ('investor', 'apartment_code', 'floor_number'), ('contract_no', 'contract_date', 'contract_value'))}),
        (_('Certificate and valuation'), {'fields': (
            ('gcn_name', 'colla_name'), ('total_value_dd', 'land_dd_value', 'builtup_value', 'value_dd'),
            ('issue_no', 'paper_issue_no'), ('dd_date', 'gcn_issue_date', 'gcn_issue_place'))}),
        (_('Notarized transfer'), {'classes': ['collapse'], 'fields': (
            ('notarize_contract_name', 'notarize_contract_no', 'notarize_contract_date'),
            ('notarize_department_name', 'notarize_transfer_no', 'notarize_transfer_date'),
            'mortgage_description')}),
    )

    def _ticket(self, obj):
        return obj.ticket if obj is not None else None


@admin.register(CollaManager)
class CollateralAdmin(MoneyInputMixin, ModelAdmin):
    """One collateral: what Sale entered, read only here, and the contract data CRA fills in."""
    list_display = ('__str__', 'colla_type', 'application')
    list_select_related = ('ticket',)
    search_fields = ('ticket__title', 'fulladdress_vn', 'car_brand')
    inlines = (CollateralContractInline,)
    fieldsets = CollateralInline.fieldsets
    autocomplete_fields = CollateralInline.autocomplete_fields

    def get_queryset(self, request):
        return super().get_queryset(request).filter(ticket__in=accessible_tickets(request.user))

    def has_module_permission(self, request):
        return False    # reached from its application

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff and (obj is None or (obj.ticket and can_access_ticket(request.user, obj.ticket)))

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_staff
        return bool(obj.ticket and editable_sections(request.user, obj.ticket) & {SALE, CRA})

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        sections = editable_sections(request.user, obj.ticket) if obj and obj.ticket else set()
        if SALE in sections:
            return ()
        return model_field_names(CollaManager, exclude=['ticket'])

    @display(description=_('Application'))
    def application(self, obj):
        return ApplicantAdmin.application(self, obj)


# ---------------------------------------------------------------- notifications

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    """The user's own notifications; opening one marks it read and goes to the application."""
    list_display = ('unread_mark', 'open_link', 'kind', 'created')
    list_display_links = None
    list_filter = (('read_at', admin.EmptyFieldListFilter), 'kind')
    actions = ('mark_selected_read',)
    actions_list = ('mark_all_read',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user=request.user).select_related('ticket', 'actor')

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff and (obj is None or obj.user_id == request.user.pk)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description='', boolean=False)
    def unread_mark(self, obj):
        return format_html('<span class="lwf-unread" title="{}"></span>', _('Unread')) if not obj.read_at else ''

    @display(description=_('Notification'))
    def open_link(self, obj):
        style = 'font-semibold' if not obj.read_at else ''
        return format_html('<a class="text-primary-600 {}" href="{}">{}</a>', style,
                           reverse('admin:lwf_notification_open', args=[obj.pk]), obj.message)

    def get_urls(self):
        return [path('<int:pk>/open/', self.admin_site.admin_view(self.open_view), name='lwf_notification_open')
                ] + super().get_urls()

    def open_view(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notifications.mark_read(request.user, Notification.objects.filter(pk=notification.pk))
        return redirect('admin:lwf_ticket_change', notification.ticket_id)

    @action(description=_('Mark as read'))
    def mark_selected_read(self, request, queryset):
        notifications.mark_read(request.user, queryset)

    @action(description=_('Mark all as read'), icon='done_all')
    def mark_all_read(self, request):
        notifications.mark_read(request.user)
        return redirect('admin:lwf_notification_changelist')


# ---------------------------------------------------------------- API and integrations (superusers)

class ApiClientForm(forms.ModelForm):
    scopes = forms.MultipleChoiceField(label=_('Scopes'), choices=ApiClient.SCOPES, required=False,
                                       widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = ApiClient
        fields = ('name', 'scopes', 'allowed_ips', 'is_active')


@admin.register(ApiClient)
class ApiClientAdmin(ModelAdmin):
    """Systems allowed to call the API. A key is shown once, when made; keep it in the other system's vault."""
    form = ApiClientForm
    list_display = ('name', 'key_prefix', 'scope_list', 'is_active', 'last_used')
    readonly_fields = ('key_prefix', 'created', 'last_used')
    actions = ('new_keys',)

    @display(description=_('Scopes'))
    def scope_list(self, obj):
        return ', '.join(obj.scopes)

    def save_model(self, request, obj, form, change):
        if not change:
            self._show_key(request, obj, obj.new_key())
        super().save_model(request, obj, form, change)

    def _show_key(self, request, obj, key):
        self.message_user(request, format_html(
            '{} <code style="user-select:all">{}</code>',
            _('Key for %s - copy it now, it is not shown again:') % obj.name, key), messages.WARNING)

    @action(description=_('Make new keys (the old ones stop working)'))
    def new_keys(self, request, queryset):
        for client in queryset:
            key = client.new_key()
            client.save(update_fields=['key_prefix', 'key_hash'])
            self._show_key(request, client, key)


class ReadOnlyAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(ReadOnlyAdmin):
    list_display = ('created', 'method', 'path', 'status', 'client', 'user', 'ip', 'duration_ms')
    list_filter = ('status', 'method', 'client')
    search_fields = ('path', 'ip')
    date_hierarchy = 'created'

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApiToken)
class ApiTokenAdmin(ReadOnlyAdmin):
    """Sign-in tokens of staff apps; delete one to sign that device out."""
    list_display = ('user', 'device', 'created', 'expires', 'last_used')
    search_fields = ('user__username', 'device')


@admin.register(Disbursement)
class DisbursementAdmin(ReadOnlyAdmin):
    list_display = ('ticket', 'reference', 'amount', 'disbursed_at', 'account_number', 'client')
    search_fields = ('ticket__title', 'reference', 'account_number')

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------- reference data (superusers)

class ImportExportAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm


class GroupManagedMixin:
    """Reference data that members of `manager_groups` maintain, besides superusers."""
    manager_groups = ()

    def _manages(self, request):
        return request.user.is_active and request.user.is_staff and (
            request.user.is_superuser or user_in_groups(request.user, *self.manager_groups))

    def has_module_permission(self, request):
        return self._manages(request)

    def has_view_permission(self, request, obj=None):
        return self._manages(request)

    def has_change_permission(self, request, obj=None):
        return self._manages(request)

    def has_add_permission(self, request):
        return self._manages(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


PANEL_MANAGERS = ('CEDOfficer', 'CEDAdmin')
PRICING_MANAGERS = ('PFSAdmin',)


@admin.register(Product)
class ProductAdmin(GroupManagedMixin, ImportExportAdmin):
    manager_groups = PRICING_MANAGERS
    list_display = ('product_code', 'product', 'subproduct_code', 'subproduct', 'crr_convert', 'order')
    search_fields = ('product', 'subproduct')


@admin.register(LoanScheme)
class LoanSchemeAdmin(GroupManagedMixin, MoneyInputMixin, ModelAdmin):
    manager_groups = PRICING_MANAGERS
    readonly_fields = ('normal',)
    list_display = ('package', 'prime', 'margin', 'normal', 'datefrom', 'dateto')
    search_fields = ('package', 'description')
    save_as = True


@admin.register(PanelProject)
class PanelProjectAdmin(GroupManagedMixin, MoneyInputMixin, ImportExportAdmin):
    manager_groups = PANEL_MANAGERS
    list_display = ('developer', 'project', 'ldname')
    search_fields = ('developer', 'project')


@admin.register(PanelCar)
class PanelCarAdmin(GroupManagedMixin, MoneyInputMixin, ImportExportAdmin):
    manager_groups = PANEL_MANAGERS
    list_display = ('brand', 'dealer', 'ldname')
    search_fields = ('brand', 'dealer')


@admin.register(Location)
class LocationAdmin(ImportExportAdmin):
    list_display = ('code_ward', 'ward', 'code_dist', 'dist', 'code_city', 'city')
    search_fields = ('ward', 'dist', 'city')
    list_per_page = 50


@admin.register(Action)
class ActionAdmin(ImportExportAdmin):
    list_display = ('description', 'apprtype', 'status', 'team', 'action_display', 'next_status', 'next_team')
    list_editable = ('apprtype', 'status', 'team', 'action_display', 'next_status', 'next_team')
    list_filter = (('apprtype', ChoicesDropdownFilter), 'status', ('team', RelatedDropdownFilter))
    list_per_page = 25
    save_as = True


@admin.register(ScoreMatrix)
class ScoreMatrixAdmin(ImportExportAdmin):
    """Rows of a version that has scored applications are read-only; copy the version to change them."""
    list_display = ('score_attr', 'description', 'value_from', 'value_to', 'value_description',
                    'score_weight', 'adjusted_score', 'scr_index', 'version')
    list_editable = ('value_from', 'value_to', 'value_description', 'score_weight', 'adjusted_score', 'scr_index')
    list_filter = ('version',)
    search_fields = ('score_attr',)
    save_as = True

    def get_changelist_instance(self, request):
        # Only a version that has not scored anything can be edited in the list.
        version = request.GET.get('version__id__exact')
        editable = version and not ScoreMatrixVersion.objects.filter(pk=version, scores__isnull=False).exists()
        self.list_editable = self.__class__.list_editable if editable else ()
        return super().get_changelist_instance(request)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.version.in_use:
            return False
        return super().has_change_permission(request, obj)

    has_delete_permission = has_change_permission


@admin.register(ScoreMatrixVersion)
class ScoreMatrixVersionAdmin(ModelAdmin):
    list_display = ('name', 'effective_from', 'is_active', 'row_count', 'scored_applications')
    readonly_fields = ('is_active', 'created')
    fields = ('name', 'effective_from', 'note', 'is_active', 'created')
    actions = ('copy_version', 'activate_version')

    @display(description=_('Rows'))
    def row_count(self, obj):
        return obj.rows.count()

    @display(description=_('Applications scored'))
    def scored_applications(self, obj):
        return obj.scores.count()

    @action(description=_('Copy as a new version'))
    def copy_version(self, request, queryset):
        for version in queryset:
            new = version.copy('%s-copy-%s' % (version.name, timezone.now().strftime('%Y%m%d%H%M%S')))
            self.message_user(request, _('Created %(new)s from %(old)s: edit its rows, then activate it.')
                              % {'new': new.name, 'old': version.name}, messages.SUCCESS)

    @action(description=_('Activate (new scores use it)'))
    def activate_version(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Choose exactly one version to activate.'), messages.ERROR)
            return
        version = queryset.get()
        version.activate()
        self.message_user(request, _('%s is now the active score matrix.') % version.name, messages.SUCCESS)

    def has_delete_permission(self, request, obj=None):
        return obj is None or not (obj.in_use or obj.is_active)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(ModelAdmin):
    """Word templates for the contracts; the help lists the placeholders a template can use."""
    list_display = ('name', 'contract_type', 'is_active', 'updated')
    list_filter = ('contract_type', 'is_active')
    readonly_fields = ('placeholders',)
    fields = ('contract_type', 'name', 'file', 'is_active', 'placeholders')

    @display(description=_('Placeholders'))
    def placeholders(self, obj):
        rows = format_html_join('', '<tr><td class="px-2 py-1"><code>{}</code></td><td class="px-2 py-1">{}</td></tr>',
                                ((names, _(meaning)) for names, meaning in contracts.PLACEHOLDERS))
        return format_html('<p class="text-sm">{}</p><table class="text-sm">{}</table>',
                           _('Write them as {{ borrower.name }}; repeat a paragraph for each item of a list '
                             'with {%p for c in collaterals %} ... {%p endfor %}. Without an active template '
                             'the built-in default is used.'), rows)


@admin.register(CreditPolicy)
class CreditPolicyAdmin(MoneyInputMixin, ModelAdmin):
    list_display = ('__str__', 'max_dsr', 'max_ltv', 'max_tenor', 'max_age_at_maturity', 'min_monthly_income',
                    'min_net_surplus', 'max_loan_amount')
    fieldsets = ((None, {'fields': ('product_code',)}),
                 (_('Limits'), {'fields': (('max_dsr', 'max_ltv'), ('max_tenor', 'max_age_at_maturity'),
                                           ('min_monthly_income', 'min_net_surplus'), 'max_loan_amount')}))


@admin.register(CreditSettings)
class CreditSettingsAdmin(MoneyInputMixin, ModelAdmin):
    """One settings row: no add once it exists, never delete."""

    def has_add_permission(self, request):
        return not CreditSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Officer)
class OfficerAdmin(ModelAdmin):
    list_display = ('user', 'mainteam', 'product', 'available')
    list_select_related = ('user', 'mainteam', 'product')
    list_editable = ('available',)

    def get_urls(self):
        toggle = path('my-availability/', self.admin_site.admin_view(self.toggle_availability),
                      name='lwf_officer_my_availability')
        return [toggle] + super().get_urls()

    @method_decorator(require_POST)
    def toggle_availability(self, request):
        """An officer switches receiving new applications (round-robin) on or off."""
        officer = get_object_or_404(Officer, user=request.user)
        officer.available = not officer.available
        officer.save(update_fields=['available', 'modified'])
        self.message_user(request, _('You now receive new applications.') if officer.available
                          else _('You no longer receive new applications.'), messages.SUCCESS)
        return redirect('admin:index')


admin.site.register(LoanEarlyRepayment, ModelAdmin)
admin.site.register(CustomerType, ModelAdmin)


# ---------------------------------------------------------------- users and roles

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
