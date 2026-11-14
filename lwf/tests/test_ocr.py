import datetime
from types import SimpleNamespace
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import translation

from lwf import ocr
from lwf.models import (Applicant, AttachDocument, CollaManager, CollateralContract, LoanDetail, SalaryIncome,
                        Ticket)


def fake_client(parsed):
    """An Anthropic client whose beta.messages.parse returns `parsed`, recording the call."""
    response = SimpleNamespace(stop_reason='end_turn', parsed_output=parsed, model='claude-opus-5-5')
    client = mock.MagicMock()
    client.beta.messages.parse.return_value = response
    return client


@override_settings(LWF_AI_DOCUMENT_READING=True)
class OcrTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(title='AP1')
        LoanDetail.objects.create(ticket=self.ticket)
        self.applicant = Applicant.objects.create(ticket=self.ticket, typeofapplicant=1, name_vn='Trần Thị Bình',
                                                  cid='079190000123')
        self.document = AttachDocument(ticket=self.ticket, related_data=2, filename='cccd.pdf')
        self.document.file.save('cccd.pdf', ContentFile(b'%PDF-1.4 test'), save=True)

    def tearDown(self):
        self.document.file.delete(save=False)

    def read(self, kind, parsed):
        client = fake_client(parsed)
        with mock.patch.object(ocr, '_client', return_value=client):
            return ocr.read(self.document, kind), client

    def test_an_id_card_is_read_and_fills_only_empty_fields(self):
        card = ocr.IdCard(full_name='TRẦN THỊ BÌNH KHÁC', id_number='079190000123', date_of_birth='1990-05-01',
                          gender='Nữ', permanent_address='12 Lê Lợi, Quận 1', issue_date='2021-07-01',
                          issue_place='Cục Cảnh sát QLHC về TTXH', expiry_date=None)
        extraction, client = self.read('id_card', card)
        kwargs = client.beta.messages.parse.call_args.kwargs
        self.assertEqual(kwargs['model'], 'claude-opus-5-5')
        self.assertEqual(kwargs['messages'][0]['content'][0]['source']['media_type'], 'application/pdf')
        self.assertEqual(kwargs['output_format'], ocr.IdCard)
        with translation.override('en'):
            states = {label: state for label, _current, _value, state in ocr.comparison(extraction)}
        self.assertEqual(states['Applicant Name'], 'differs')
        self.assertEqual(ocr.apply(extraction), 4)   # dob, address, issue date, issue place
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.name_vn, 'Trần Thị Bình')     # a differing value is left alone
        self.assertEqual(self.applicant.dob, datetime.date(1990, 5, 1))
        self.assertEqual(self.applicant.cra_id_place, 'Cục Cảnh sát QLHC về TTXH')

    def test_a_payslip_becomes_a_salary_record(self):
        slip = ocr.Payslip(employee_name='Trần Thị Bình', employer='Công ty Demo', job_title='Kế toán',
                           months=[
            ocr.PayMonth(month='2026-10', fixed_pay=30_000_000, variable_pay=2_000_000),
            ocr.PayMonth(month='2026-09', fixed_pay=30_000_000, variable_pay=0)])
        extraction, _client = self.read('payslip', slip)
        ocr.apply(extraction)
        salary = SalaryIncome.objects.get(applicant=self.applicant)
        self.assertEqual((salary.employer, salary.fix_avg, salary.var_avg), ('Công ty Demo', 30_000_000, 1_000_000))

    def test_a_land_certificate_fills_the_collateral_contract_data(self):
        CollaManager.objects.create(ticket=self.ticket)
        cert = ocr.LandCertificate(certificate_title='GCN', serial_number='CS 123456', register_number='VP 01',
                                   issue_date='2020-01-15', issue_place='Sở TN&MT', owners=['Trần Thị Bình'],
                                   land_plot='45', map_sheet='12', address='Phường 1', land_area_m2=80.5,
                                   land_use_purpose='Đất ở', land_use_term='Lâu dài',
                                   land_use_origin='Nhận chuyển nhượng', floor_area_m2=None)
        extraction, _client = self.read('land_certificate', cert)
        ocr.apply(extraction)
        legal = CollateralContract.objects.get()
        self.assertEqual((legal.land_plot, legal.land_map, legal.issue_no), ('45', '12', 'CS 123456'))

    @override_settings(LWF_AI_DOCUMENT_READING=False)
    def test_nothing_is_sent_when_turned_off(self):
        extraction, client = self.read('id_card', None)
        self.assertTrue(extraction.error)
        client.beta.messages.parse.assert_not_called()

    def test_only_pdf_and_images(self):
        self.document.file.save('scan.docx', ContentFile(b'x'), save=True)
        extraction, client = self.read('id_card', None)
        self.assertIn('PDF', extraction.error)
        client.beta.messages.parse.assert_not_called()
