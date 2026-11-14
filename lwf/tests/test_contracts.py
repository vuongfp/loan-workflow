import io

from django.test import TestCase
from docx import Document

from lwf import contracts
from lwf.models import Applicant, CollaManager, CraDocInfo, LoanContract, LoanDetail, Ticket


class ContractTests(TestCase):
    def setUp(self):
        self.ticket = Ticket.objects.create(title='DS.SS.26.0001')
        Applicant.objects.create(ticket=self.ticket, typeofapplicant=1, name_vn='Nguyễn Văn A', cid='079000000001')
        LoanDetail.objects.create(ticket=self.ticket, loanamount=1_500_000_000, loan_tenor=240)
        LoanContract.objects.create(ticket=self.ticket, loan_amount=1_500_000_000, credit_limit=1_500_000_000)
        CollaManager.objects.create(ticket=self.ticket, colla_type=2, spa_or_estimated=2_000_000_000)

    def text(self, contract_type):
        doc = CraDocInfo.objects.create(ticket=self.ticket, contract_type=contract_type, contract_number='FA-1')
        return '\n'.join(p.text for p in Document(io.BytesIO(contracts.contract_docx(doc))).paragraphs)

    def test_every_default_template_is_filled(self):
        for contract_type in contracts.DEFAULT_FILES:
            text = self.text(contract_type)
            self.assertNotIn('{{', text)
            self.assertNotIn('{%', text)
            self.assertIn('Nguyễn Văn A', text)

    def test_amounts_are_written_in_words(self):
        text = self.text(1)
        self.assertIn('1,500,000,000 VND (Một tỷ năm trăm triệu đồng)', text)
        self.assertIn('Hai tỷ đồng', text)   # the collateral value
