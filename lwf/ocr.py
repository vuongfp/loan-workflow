"""
Reading uploaded documents with AI (Claude): the ID card, a payslip or a land
certificate becomes structured fields. A person compares them with the
application and applies them; nothing is changed without that step.

The document is sent to the Anthropic API, so the feature is off unless
LWF_AI_DOCUMENT_READING is set (and the bank has agreed to it); the API key
comes from the environment (ANTHROPIC_API_KEY).
"""
import base64
import mimetypes
import os
from typing import Optional

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from pydantic import BaseModel, Field

from lwf.models import Applicant, CollaManager, CollateralContract, DocumentExtraction, SalaryIncome

MAX_BYTES = 30 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


# ------------------------------------------------------------ what is read from each kind of document

class IdCard(BaseModel):
    full_name: Optional[str] = Field(description='Họ và tên, as printed, with Vietnamese accents')
    id_number: Optional[str] = Field(description='Số định danh / số CCCD, digits only')
    date_of_birth: Optional[str] = Field(description='Ngày sinh as YYYY-MM-DD')
    gender: Optional[str] = Field(description='Nam or Nữ')
    permanent_address: Optional[str] = Field(description='Nơi thường trú')
    issue_date: Optional[str] = Field(description='Ngày cấp as YYYY-MM-DD')
    issue_place: Optional[str] = Field(description='Nơi cấp / cơ quan cấp')
    expiry_date: Optional[str] = Field(description='Có giá trị đến, YYYY-MM-DD')


class PayMonth(BaseModel):
    month: str = Field(description='YYYY-MM')
    fixed_pay: Optional[int] = Field(description='Fixed salary of the month in VND, whole number')
    variable_pay: Optional[int] = Field(description='Bonus, allowances, overtime of the month in VND')


class Payslip(BaseModel):
    employee_name: Optional[str]
    employer: Optional[str] = Field(description='Employer company name')
    job_title: Optional[str]
    months: list[PayMonth] = Field(description='One entry per month shown, newest first')


class LandCertificate(BaseModel):
    certificate_title: Optional[str] = Field(description='Title of the certificate as printed')
    serial_number: Optional[str] = Field(description='Số phát hành (series such as CS 123456)')
    register_number: Optional[str] = Field(description='Số vào sổ cấp GCN')
    issue_date: Optional[str] = Field(description='Ngày cấp as YYYY-MM-DD')
    issue_place: Optional[str] = Field(description='Cơ quan cấp')
    owners: list[str] = Field(description='Names of the owners')
    land_plot: Optional[str] = Field(description='Thửa đất số')
    map_sheet: Optional[str] = Field(description='Tờ bản đồ số')
    address: Optional[str] = Field(description='Địa chỉ thửa đất')
    land_area_m2: Optional[float]
    land_use_purpose: Optional[str] = Field(description='Mục đích sử dụng')
    land_use_term: Optional[str] = Field(description='Thời hạn sử dụng')
    land_use_origin: Optional[str] = Field(description='Nguồn gốc sử dụng')
    floor_area_m2: Optional[float] = Field(description='House floor area, if a house is listed')


KINDS = {
    'id_card': (gettext_lazy('ID card (CCCD)'), IdCard),
    'payslip': (gettext_lazy('Payslip or salary statement'), Payslip),
    'land_certificate': (gettext_lazy('Land / house certificate'), LandCertificate),
}
# Document group (AttachDocument.related_data) -> the kind read by default.
KIND_BY_GROUP = {2: 'id_card', 3: 'payslip', 4: 'land_certificate'}

PROMPT = (
    'You read a Vietnamese bank loan document ({kind}). Return the fields exactly as printed, keeping '
    'Vietnamese accents. Dates as YYYY-MM-DD, money as whole VND numbers without separators. If a field is '
    'not on the document or cannot be read with confidence, return null for it - never guess.')


class ReadingError(Exception):
    pass


def enabled():
    return bool(getattr(settings, 'LWF_AI_DOCUMENT_READING', False))


def default_kind(document):
    return KIND_BY_GROUP.get(document.related_data)


def _content_block(document):
    name = document.file.name
    media_type = mimetypes.guess_type(name)[0] or ''
    with document.file.open('rb') as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ReadingError(_('The file is larger than 30 MB.'))
    encoded = base64.standard_b64encode(data).decode('ascii')
    if media_type == 'application/pdf':
        return {'type': 'document', 'source': {'type': 'base64', 'media_type': media_type, 'data': encoded}}
    if media_type in IMAGE_TYPES:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': encoded}}
    raise ReadingError(_('Only PDF and image files (JPEG, PNG, GIF, WebP) can be read.'))


def _client():
    import anthropic
    return anthropic.Anthropic()


def read(document, kind, user=None):
    """Send the document to Claude and store what it read (DocumentExtraction), or the error."""
    import anthropic

    label, schema = KINDS[kind]
    model = getattr(settings, 'LWF_AI_MODEL', 'claude-opus-5-5')
    extraction = DocumentExtraction(document=document, kind=kind, model_name=model, created_by=user)
    try:
        if not enabled():
            raise ReadingError(_('AI document reading is turned off (LWF_AI_DOCUMENT_READING).'))
        response = _client().beta.messages.parse(
            model=model,
            max_tokens=16000,
            # If the model declines, the API retries on another model in the same call.
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            messages=[{'role': 'user', 'content': [
                _content_block(document),
                {'type': 'text', 'text': PROMPT.format(kind=str(KINDS[kind][0]))},
            ]}],
            output_format=schema,
        )
        if response.stop_reason == 'refusal' or response.parsed_output is None:
            raise ReadingError(_('The AI could not read this document.'))
        extraction.data = response.parsed_output.model_dump(mode='json')
        extraction.model_name = response.model
    except ReadingError as error:
        extraction.error = str(error)
    except anthropic.APIConnectionError:
        extraction.error = _('The AI service could not be reached; try again later.')
    except anthropic.RateLimitError:
        extraction.error = _('The AI service is busy; try again in a minute.')
    except anthropic.APIStatusError as error:
        extraction.error = _('The AI service answered with an error (%s).') % error.status_code
    extraction.save()
    return extraction


# ------------------------------------------------------------ comparing and applying

def _date(text):
    try:
        return timezone.datetime.strptime(text, '%Y-%m-%d').date() if text else None
    except ValueError:
        return None


def _targets(extraction):
    """(label, object, field, current value, value read) for every field a reading can fill."""
    ticket = extraction.document.ticket
    data = extraction.data
    rows = []
    if extraction.kind == 'id_card':
        applicant = (Applicant.objects.filter(ticket=ticket, cid=data.get('id_number')).first()
                     or Applicant.objects.filter(ticket=ticket, typeofapplicant=1).first())
        if applicant:
            for label, field, value in (
                    (_('Applicant Name'), 'name_vn', data.get('full_name')),
                    (_('Applicant ID'), 'cid', data.get('id_number')),
                    (_('Date of Birth'), 'dob', _date(data.get('date_of_birth'))),
                    (_('Permanent address'), 'permanent_address_vn', data.get('permanent_address')),
                    (_('ID issue date'), 'cra_id_date', _date(data.get('issue_date'))),
                    (_('ID issue place'), 'cra_id_place', data.get('issue_place'))):
                rows.append((label, applicant, field, getattr(applicant, field), value))
    elif extraction.kind == 'land_certificate':
        collateral = CollaManager.objects.filter(ticket=ticket).order_by('pk').first()
        if collateral:
            legal, _created = CollateralContract.objects.get_or_create(collateral=collateral)
            for label, field, value in (
                    (_('Land plot'), 'land_plot', data.get('land_plot')),
                    (_('Land map'), 'land_map', data.get('map_sheet')),
                    (_('Land area/GFA (m2)'), 'land_area', data.get('land_area_m2')),
                    (_('Full Address'), 'fulladdress', data.get('address')),
                    (_('Certificate serial number'), 'issue_no', data.get('serial_number')),
                    (_('Certificate register number'), 'paper_issue_no', data.get('register_number')),
                    (_('Certificate issue date'), 'gcn_issue_date', _date(data.get('issue_date'))),
                    (_('Certificate issued by'), 'gcn_issue_place', data.get('issue_place')),
                    (_('Land use purpose'), 'land_using_purpose', data.get('land_use_purpose')),
                    (_('Land use term'), 'land_using_time', data.get('land_use_term')),
                    (_('Land use origin'), 'land_using_source', data.get('land_use_origin'))):
                rows.append((label, legal, field, getattr(legal, field), value))
    return rows


def comparison(extraction):
    """Rows for the review page: what the application has and what was read."""
    if extraction.kind == 'payslip':
        months = extraction.data.get('months') or []
        return [(m.get('month'), '', '{:,}'.format((m.get('fixed_pay') or 0) + (m.get('variable_pay') or 0)), 'new')
                for m in months]
    rows = []
    for label, _obj, _field, current, value in _targets(extraction):
        state = 'same' if value in (None, '') or str(current) == str(value) else ('new' if not current else 'differs')
        rows.append((label, current if current not in (None, '') else '', value if value is not None else '', state))
    return rows


def apply(extraction):
    """
    Fill the application from a reading: empty fields only (a differing value
    stays for a person to change); for a payslip, a new salary record on the
    primary applicant. Returns how many fields were filled.
    """
    filled = 0
    if extraction.kind == 'payslip':
        filled = _apply_payslip(extraction)
    else:
        changed = {}
        for _label, obj, field, current, value in _targets(extraction):
            if value not in (None, '') and current in (None, ''):
                setattr(obj, field, value)
                changed.setdefault(obj, []).append(field)
                filled += 1
        for obj, fields in changed.items():
            obj.save(update_fields=fields)
    extraction.applied_at = timezone.now()
    extraction.save(update_fields=['applied_at'])
    return filled


def _apply_payslip(extraction):
    from lwf import services

    ticket = extraction.document.ticket
    applicant = Applicant.objects.filter(ticket=ticket, typeofapplicant=1).first()
    months = (extraction.data.get('months') or [])[:12]
    if not applicant or not months:
        return 0
    record = SalaryIncome(applicant=applicant, employer=extraction.data.get('employer') or '',
                          designation=extraction.data.get('job_title') or '', monthamt=len(months),
                          varmonthamt=len(months), contract_type=1, payment_type=1)
    for index, month in enumerate(months, start=1):
        setattr(record, 'fix_m%d' % index, month.get('fixed_pay') or 0)
        setattr(record, 'var_m%d' % index, month.get('variable_pay') or 0)
    record.save()
    services.recalc_credit_summary(ticket)
    return len(months)


def file_name(extraction):
    return os.path.basename(extraction.document.file.name)
