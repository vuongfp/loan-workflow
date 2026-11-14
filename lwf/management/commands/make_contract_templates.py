"""
Write the default Word contract templates to lwf/contract_templates/. They are
a starting point: the business replaces them with its own wording by uploading
a ContractTemplate in the admin, using the same placeholders.
"""
import os

from django.core.management.base import BaseCommand
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from lwf.contracts import DEFAULT_DIR, DEFAULT_FILES

PARTIES = [
    ('h', 'BÊN CHO VAY (sau đây gọi là "Ngân Hàng")'),
    ('p', 'Tên: {{ lender.name }}'),
    ('p', 'Địa chỉ: {{ lender.address }}'),
    ('p', 'Mã số doanh nghiệp: {{ lender.registration }}'),
    ('p', 'Đại diện: {{ contract.signer }}        Chức vụ: {{ contract.position }}'),
    ('h', 'BÊN VAY (sau đây gọi là "Bên Vay")'),
    ('p', 'Họ và tên: {{ borrower.name }}        Ngày sinh: {{ borrower.dob }}'),
    ('p', 'Số CCCD/CMND: {{ borrower.id_number }}, cấp ngày {{ borrower.id_date }} tại {{ borrower.id_place }}'),
    ('p', 'Địa chỉ thường trú: {{ borrower.permanent_address }}'),
    ('p', 'Địa chỉ liên lạc: {{ borrower.current_address }}'),
    ('p', '{%p for person in co_borrowers %}'),
    ('p', 'Người đồng vay: {{ person.name }}, CCCD/CMND {{ person.id_number }}, địa chỉ {{ person.permanent_address }}'),
    ('p', '{%p endfor %}'),
]

COLLATERALS = [
    ('p', '{%p for c in collaterals %}'),
    ('p', 'Tài sản {{ loop.index }}: {{ c.type }} tại {{ c.address }}'),
    ('p', 'Thửa đất số {{ c.land_plot }}, tờ bản đồ số {{ c.land_map }}, diện tích {{ c.land_area }} m2; '
          '{{ c.certificate }} số {{ c.certificate_number }}, cấp ngày {{ c.certificate_date }} tại {{ c.certificate_place }}.'),
    ('p', 'Giá trị: {{ c.value }} VND ({{ c.value_words }}).'),
    ('p', '{%p endfor %}'),
]

SIGNATURES = [
    ('p', ''),
    ('p', 'Lập ngày {{ contract.sign_date or today }}, thành hai bản có giá trị như nhau, mỗi bên giữ một bản.'),
    ('h', 'ĐẠI DIỆN NGÂN HÀNG                                        BÊN VAY'),
    ('p', '{{ contract.signer }}                                                    {{ borrower.name }}'),
]

TEMPLATES = {
    1: ('HỢP ĐỒNG TÍN DỤNG', PARTIES + [
        ('h', 'ĐIỀU 1. KHOẢN VAY'),
        ('p', 'Số tiền cho vay: {{ loan.amount }} VND ({{ loan.amount_words }}).'),
        ('p', 'Hạn mức tín dụng: {{ loan.credit_limit }} VND ({{ loan.credit_limit_words }}).'),
        ('p', 'Mục đích sử dụng vốn: {{ loan.purpose }}.'),
        ('p', 'Thời hạn cho vay: {{ loan.tenor }} tháng kể từ ngày giải ngân đầu tiên.'),
        ('h', 'ĐIỀU 2. LÃI SUẤT VÀ PHÍ'),
        ('p', 'Lãi suất: {{ loan.interest_rate }}%/năm; biên độ sau thời gian ưu đãi: {{ loan.margin }}%/năm.'),
        ('p', 'Phí trả nợ trước hạn: {{ loan.early_repayment_fee }}.'),
        ('h', 'ĐIỀU 3. GIẢI NGÂN'),
        ('p', 'Số tiền giải ngân: {{ loan.disbursement_amount }} VND; phương thức: {{ loan.disbursement_method }}.'),
        ('h', 'ĐIỀU 4. BẢO ĐẢM TIỀN VAY'),
    ] + COLLATERALS + [
        ('h', 'ĐIỀU 5. ĐIỀU KIỆN KHÁC'),
        ('p', '{{ loan.conditions }}'),
    ] + SIGNATURES),
    2: ('HỢP ĐỒNG THẾ CHẤP', PARTIES + [
        ('h', 'ĐIỀU 1. NGHĨA VỤ ĐƯỢC BẢO ĐẢM'),
        ('p', 'Toàn bộ nghĩa vụ trả nợ của Bên Vay theo hồ sơ vay số {{ application.number }}, số tiền vay '
              '{{ loan.amount }} VND ({{ loan.amount_words }}).'),
        ('h', 'ĐIỀU 2. TÀI SẢN THẾ CHẤP'),
    ] + COLLATERALS + SIGNATURES),
    3: ('HỢP ĐỒNG BA BÊN', PARTIES + [
        ('h', 'BÊN BÁN'),
        ('p', '{%p for s in sellers %}'),
        ('p', '{{ s.name }}, sinh năm {{ s.birth_year }}, CCCD/CMND {{ s.id_number }} cấp tại {{ s.id_place }}, '
              'địa chỉ {{ s.address }}'),
        ('p', '{%p endfor %}'),
        ('h', 'NỘI DUNG'),
        ('p', 'Ngân Hàng giải ngân {{ loan.disbursement_amount }} VND trực tiếp cho Bên Bán để thanh toán tiền mua '
              'tài sản sau cho Bên Vay:'),
    ] + COLLATERALS + SIGNATURES),
    4: ('BIÊN BẢN ĐỊNH GIÁ TÀI SẢN', PARTIES + [
        ('h', 'KẾT QUẢ ĐỊNH GIÁ'),
    ] + COLLATERALS + SIGNATURES),
}


def build(path, title, lines):
    document = Document()
    style = document.styles['Normal']
    style.font.name, style.font.size = 'Times New Roman', Pt(12)
    for text in ('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', 'Độc lập - Tự do - Hạnh phúc', '', title,
                 'Số: {{ contract.number }}'):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        run.bold = text in (title, 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM')
        if text == title:
            run.font.size = Pt(15)
    for kind, text in lines:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(text)
        run.bold = kind == 'h'
    document.save(path)


class Command(BaseCommand):
    help = 'Write the default Word contract templates to lwf/contract_templates/.'

    def handle(self, *args, **options):
        os.makedirs(DEFAULT_DIR, exist_ok=True)
        for contract_type, (title, lines) in TEMPLATES.items():
            path = os.path.join(DEFAULT_DIR, DEFAULT_FILES[contract_type])
            build(path, title, lines)
            self.stdout.write(path)
