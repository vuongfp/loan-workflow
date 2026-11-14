"""
Demo data: users for every role and synthetic loan applications at every step
of the workflow. Nothing here comes from real customers; names, ID numbers,
employers and amounts are generated.

Applications are moved through the real workflow (lwf.workflow.transition), so
their history, numbering and role fields are what the app itself produces.
"""
import datetime
import os
import random
from dataclasses import dataclass

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from lwf import completeness, services, workflow
from lwf.models import (LOV, Action, Applicant, AttachDocument, CicCreditCard, CicSecureLoan, CicUnSecureLoan, CollaManager,
                        CollateralContract, Condition, CraDocInfo, CreditDecision, Disbursement, FollowUp, LoanContract,
                        LoanDetail, LoanScheme, Location, Notification, Officer, PanelCar, PanelProject, SalaryIncome,
                        BusinessIncome, Ticket)

# (username, full name, groups, officer team for round-robin assignment)
USERS = [
    ('sale1', 'Nguyễn Minh Khang', ['SaleTeam'], None),
    ('sale2', 'Trần Thu Hà', ['SaleTeam'], None),
    ('salelead', 'Lê Quốc Bảo', ['SaleManager'], None),
    ('salesupport', 'Phạm Ngọc Anh', ['SaleSupport'], None),
    ('saledirector', 'Võ Thành Đạt', ['SaleDirector'], None),
    ('headpfs', 'Đặng Thị Lan', ['HeadPFS'], None),
    ('ced1', 'Hoàng Gia Huy', ['CEDOfficer'], 'CEDOfficer'),
    ('ced2', 'Bùi Mai Phương', ['CEDOfficer'], 'CEDOfficer'),
    ('cedadmin', 'Đỗ Hữu Tâm', ['CEDOfficer', 'CEDAdmin'], None),
    ('approver1', 'Ngô Đức Thịnh', ['Approver'], None),
    ('approver2', 'Dương Kim Ngân', ['Approver'], None),
    ('cra1', 'Nguyễn Văn An', ['CRAOfficer'], 'CRAOfficer'),
    ('craadmin', 'Trịnh Bảo Châu', ['CRAOfficer', 'CRAAdmin'], None),
]

# Where each demo application stops: the statuses it passes through after Open.
SUBMIT = [Ticket.ENDORSE_STATUS, Ticket.SUPPORT_STATUS]
TO_CED = SUBMIT + [Ticket.VERIFY_STATUS]
APPROVED = TO_CED + [Ticket.APPROVER1_STATUS, Ticket.APPROVER2_STATUS, Ticket.POST_APPROVAL]
DISBURSED = APPROVED + [Ticket.DOCSPREP_STATUS, Ticket.CONFIRMFDISB_STATUS, Ticket.DISBURSEMENT_STATUS,
                        Ticket.COMPLETE_STATUS]
ROUTES = [
    [],                                                                     # Open, Sale still entering
    SUBMIT[:1],                                                             # with the sale leader
    SUBMIT,                                                                 # with sale support
    SUBMIT + [Ticket.SS_RQ_UPDATE],                                         # back to Sale for an update
    SUBMIT + [Ticket.SD_APPROVE_EXCEPTION],                                 # exception: head of sale
    SUBMIT + [Ticket.SD_APPROVE_EXCEPTION, Ticket.HS_APPROVE_EXCEPTION],    # exception: head of PFS
    TO_CED,                                                                 # CED verifying
    TO_CED + [Ticket.CED_RQ_UPDATE],                                        # CED asked Sale for more
    TO_CED + [Ticket.APPROVER1_STATUS],                                     # first approval
    TO_CED + [Ticket.APPROVER1_STATUS, Ticket.APPROVER2_STATUS],            # second approval
    APPROVED,                                                               # approved, Sale to proceed
    APPROVED + [Ticket.DOCSPREP_STATUS],                                    # CRA preparing documents
    APPROVED + [Ticket.DOCSPREP_STATUS, Ticket.CONFIRMFDISB_STATUS],        # Sale to confirm disbursement
    DISBURSED[:-1],                                                         # CRA disbursing
    DISBURSED,                                                              # complete
    TO_CED + [Ticket.REJECT_STATUS],                                        # rejected by CED
    [Ticket.CLOSED_STATUS],                                                 # cancelled by Sale
    DISBURSED,
]

FAMILY = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ', 'Đặng', 'Bùi', 'Đỗ', 'Hồ',
          'Ngô', 'Dương', 'Lý']
MIDDLE = {1: ['Văn', 'Minh', 'Quốc', 'Hữu', 'Đức', 'Thành'], 2: ['Thị', 'Ngọc', 'Thu', 'Kim', 'Mỹ', 'Thanh']}
GIVEN = {1: ['An', 'Bình', 'Cường', 'Dũng', 'Hải', 'Hiếu', 'Khoa', 'Long', 'Nam', 'Phúc', 'Quân', 'Sơn', 'Tuấn',
             'Việt'],
         2: ['Anh', 'Chi', 'Dung', 'Giang', 'Hạnh', 'Hương', 'Linh', 'Mai', 'Nhung', 'Oanh', 'Thảo', 'Trang',
             'Vy', 'Yến']}
STREETS = ['Lê Lợi', 'Nguyễn Huệ', 'Hai Bà Trưng', 'Điện Biên Phủ', 'Cách Mạng Tháng Tám', 'Lý Thường Kiệt',
           'Nguyễn Trãi', 'Trần Hưng Đạo', 'Võ Văn Tần', 'Phan Đình Phùng']
EMPLOYERS = ['Công ty TNHH Demo Sao Mai', 'Công ty CP Demo Bình Minh', 'Công ty TNHH Demo Hưng Thịnh',
             'Công ty CP Demo Phương Đông', 'Công ty TNHH Demo Tân Tiến']
TITLES = ['Kế toán trưởng', 'Trưởng phòng kinh doanh', 'Kỹ sư phần mềm', 'Quản lý dự án', 'Chuyên viên tài chính']
CONDITIONS = ['Bổ sung sao kê lương 3 tháng gần nhất trước giải ngân.',
              'Mua bảo hiểm tài sản thế chấp, ngân hàng là người thụ hưởng.',
              'Hoàn tất đăng ký giao dịch bảo đảm trước giải ngân.',
              'Khách hàng ký cam kết không bán tài sản trong thời gian vay.']


def demo_pdf(title):
    """A one-page PDF that says it is a demo document."""
    text = ('DEMO - %s' % title).encode('ascii', 'replace').decode().replace('(', '[').replace(')', ']')
    stream = 'BT /F1 14 Tf 60 780 Td (%s) Tj ET' % text
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R '
               '/Resources << /Font << /F1 5 0 R >> >> >>',
               '<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream),
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, offsets = '%PDF-1.4\n', []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += '%d 0 obj\n%s\nendobj\n' % (number, body)
    xref = len(out)
    out += 'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
    out += ''.join('%010d 00000 n \n' % offset for offset in offsets)
    out += 'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    return out.encode('latin-1')


@dataclass
class Seeded:
    users: int
    applications: int


def create_users(password):
    """The demo users, one or more per role; returns {username: user}."""
    users = {}
    for username, full_name, groups, officer_team in USERS:
        family, *rest = full_name.split()
        user, _created = User.objects.update_or_create(
            username=username, defaults={'first_name': ' '.join(rest), 'last_name': family, 'is_staff': True,
                                         'is_active': True, 'email': ''})
        user.set_password(password)
        user.save()
        user.groups.set(Group.objects.filter(name__in=groups))
        if officer_team:
            Officer.objects.update_or_create(user=user, defaults={
                'mainteam': Group.objects.get(name=officer_team), 'available': True})
        users[username] = user
    return users


def create_superuser(username, password):
    user, _created = User.objects.get_or_create(username=username)
    user.is_staff = user.is_superuser = user.is_active = True
    user.set_password(password)
    user.save()
    return user


def delete_demo_data():
    """All applications (and what hangs off them, uploaded files included) and the demo users."""
    folders = set()
    for document in AttachDocument.objects.exclude(file=''):
        if document.file.storage.exists(document.file.name):
            folders.add(os.path.dirname(document.file.path))
        document.file.delete(save=False)
    for folder in folders:
        try:
            os.rmdir(folder)    # only when empty
        except OSError:
            pass
    Disbursement.objects.all().delete()    # protects its application
    Ticket.objects.all().delete()
    User.objects.filter(username__in=[u[0] for u in USERS]).delete()


class ApplicationFactory:
    def __init__(self, rng, users):
        self.rng = rng
        self.users = users
        self.locations = list(Location.objects.filter(code_city__in=(1, 79)).values('ward', 'dist', 'city')[:400])
        self.schemes = list(LoanScheme.objects.all())
        self.projects = list(PanelProject.objects.all())
        self.dealers = list(PanelCar.objects.all())

    # ------------------------------------------------------------ Sale data

    def person(self):
        gender = self.rng.choice((1, 2))
        name = ' '.join((self.rng.choice(FAMILY), self.rng.choice(MIDDLE[gender]), self.rng.choice(GIVEN[gender])))
        dob = datetime.date(self.rng.randint(1970, 1998), self.rng.randint(1, 12), self.rng.randint(1, 28))
        # 12-digit citizen ID: province, century/gender digit, year, then random digits.
        cid = '079%d%02d%06d' % ((0 if gender == 1 else 1), dob.year % 100, self.rng.randint(0, 999999))
        return gender, name, dob, cid

    def address(self):
        place = self.rng.choice(self.locations) if self.locations else {'ward': '', 'dist': '', 'city': ''}
        return '%d %s, %s, %s, %s' % (self.rng.randint(1, 250), self.rng.choice(STREETS), place['ward'],
                                      place['dist'], place['city'])

    def applicant(self, ticket, kind):
        gender, name, dob, cid = self.person()
        address = self.address()
        applicant = Applicant(
            ticket=ticket, typeofapplicant=kind, name_vn=name, cid=cid, dob=dob, gender=gender, nationality=1,
            marital=self.rng.choice((1, 2)), edulvl=self.rng.randint(2, 4), typehouse=self.rng.randint(1, 3),
            resstat=self.rng.randint(1, 3), reslocation=1, relationship_bank=self.rng.choice((0, 0, 1)),
            relatedparty=0, permanent_address_vn=address, temporary_address_vn=address,
            cicdate=timezone.localdate() - datetime.timedelta(days=self.rng.randint(3, 20)),
            cic5Y=self.rng.choice(('NoCIC', 'G1', 'G1', 'G1')))
        services.normalize_applicant(applicant)
        applicant.save()
        if kind == 1 or self.rng.random() < 0.6:
            self.salary(applicant)
        if kind == 1 and self.rng.random() < 0.3:
            self.business(applicant)
        if self.rng.random() < 0.5:
            self.credit_records(applicant)
        return applicant

    def salary(self, applicant):
        monthly = self.rng.randrange(35, 120) * 1_000_000
        record = SalaryIncome(applicant=applicant, employer=self.rng.choice(EMPLOYERS),
                              designation=self.rng.choice(TITLES), length_in_service=self.rng.randint(12, 120),
                              contract_type=1, payment_type=1, monthamt=3, varmonthamt=3)
        for month in (1, 2, 3):
            setattr(record, 'fix_m%d' % month, monthly)
            setattr(record, 'var_m%d' % month, self.rng.randrange(0, 10) * 1_000_000)
        record.save()

    def business(self, applicant):
        turnover = self.rng.randrange(3, 15) * 1_000_000_000
        BusinessIncome.objects.create(
            applicant=applicant, name='Hộ kinh doanh Demo %s' % applicant.name_vn.split()[-1], shareportion=100,
            years=self.rng.randint(2, 10), industry=1, industrydetail=101, vat_period=12,
            vat_amount=turnover, bank_statement_amount=turnover, year3_sales_turnover=turnover, EBITDAmargin=12)

    def credit_records(self, applicant):
        amount = self.rng.randrange(2, 8) * 100_000_000
        CicSecureLoan.objects.create(applicant=applicant, original_amount=amount, interest_rate=10.5,
                                     loan_tenor=self.rng.choice((120, 180, 240)),
                                     outstanding_loan=amount * self.rng.randint(30, 90) // 100)
        if self.rng.random() < 0.5:
            balances = {'bm%d' % i: self.rng.randrange(2, 40) * 1_000_000 for i in range(1, 7)}
            CicCreditCard.objects.create(applicant=applicant, **balances)
        if self.rng.random() < 0.3:
            CicUnSecureLoan.objects.create(applicant=applicant, m1=3_000_000, m2=3_000_000, m3=3_000_000)

    def loan_and_collateral(self, ticket):
        car = self.rng.random() < 0.3
        loan = LoanDetail.objects.get(ticket=ticket)
        collateral = CollaManager.objects.get(ticket=ticket)
        if car:
            price = self.rng.randrange(6, 25) * 100_000_000
            dealer = self.rng.choice(self.dealers) if self.dealers else None
            loan.product, loan.subproduct, loan.purpose = 6, 61, 5
            loan.loanamount = price * self.rng.choice((60, 70, 80)) // 100
            loan.loan_tenor = self.rng.choice((48, 60, 72, 84))
            collateral.car_brand = dealer.brand if dealer else 'Toyota'
            collateral.car_model = self.rng.choice(('Sedan', 'SUV', 'MPV'))
            collateral.car_year = timezone.localdate().year
            collateral.car_spa_value = price
            collateral.car_dealer = dealer
        else:
            price = self.rng.randrange(15, 40) * 100_000_000
            project = self.rng.choice(self.projects) if self.projects and self.rng.random() < 0.5 else None
            loan.product, loan.subproduct = (2, 21) if project else (1, 11)
            loan.purpose = 1 if project else 2
            loan.loanamount = price * self.rng.choice((50, 60, 70)) // 100
            loan.loan_tenor = self.rng.choice((240, 300))
            collateral.mortgage_type = 12 if project else 1
            collateral.title_deed = 0 if project else 1
            collateral.existing_collateral, collateral.address_available = 0, 1
            collateral.spa_or_estimated = price
            collateral.fulladdress_vn = self.address()
            collateral.land_area = self.rng.randint(50, 150)
            collateral.built_up_area = collateral.land_area * self.rng.randint(2, 4)
            collateral.construction_status = 2
            collateral.occupancy = 1
            collateral.project_name = project
            if project:
                collateral.project_developer = project.developer
        loan.loan_moa = round(loan.loanamount * 100 / price)
        loan.loan_pricing_scheme = self.rng.choice(self.schemes) if self.schemes else None
        loan.loanprogram = 1
        loan.sale_note = 'Hồ sơ demo, dữ liệu tự sinh.'
        loan.save()
        collateral.save()
        services.apply_loan_change(loan)

    def build(self, submitter):
        ticket = services.create_application(submitter)
        ticket.description = 'Hồ sơ vay demo'
        ticket.save(update_fields=['description'])
        for kind in [1] + [2] * self.rng.choice((0, 0, 1)):
            self.applicant(ticket, kind)
        self.loan_and_collateral(ticket)
        self.documents(ticket)
        services.recalc_credit_summary(ticket)
        return ticket

    def documents(self, ticket):
        """A placeholder PDF for each document group the application needs."""
        names = dict(LOV.RELATED_DATA_CHOICES)
        for group in completeness.REQUIRED_DOCUMENT_GROUPS:
            name = 'demo-%d.pdf' % group
            document = AttachDocument(ticket=ticket, related_data=group, filename=name)
            document.file.save(name, ContentFile(demo_pdf(str(names[group]))), save=True)

    # ------------------------------------------------------------ CED and CRA data

    def credit_review(self, ticket):
        """What CED fills in before recommending: the CRR score, the decision and conditions."""
        services.score_application(ticket, {
            'age_borrower_acc': self.rng.choice((0, 1, 3, 4)), 'conduct_acc': self.rng.choice((0, 1, 1)),
            'where_report': 1, 'num_CI': self.rng.randint(0, 3), 'no12_Defaults': 0, 'no60_Defaults': 0})
        loan = LoanDetail.objects.get(ticket=ticket)
        collateral = CollaManager.objects.filter(ticket=ticket).first()
        value = (collateral.spa_or_estimated or collateral.car_spa_value or 0) if collateral else 0
        decision = CreditDecision.objects.get(ticket=ticket)
        decision.approved_amount = loan.loanamount
        decision.desktop_valuation = value
        decision.report_valuation = value * self.rng.randint(95, 105) // 100
        decision.portfolio_capping = 0
        decision.recommendation = ('Thu nhập ổn định, DSR trong giới hạn, tài sản bảo đảm đủ điều kiện. '
                                   'Đề xuất phê duyệt %s VND trong %s tháng.' % (
                                       '{:,}'.format(loan.loanamount), loan.loan_tenor))
        decision.save()
        for text in self.rng.sample(CONDITIONS, 2):
            Condition.objects.create(ticket=ticket, condition_type=1, condition_detail=text, dox_type=1)

    def approver_comment(self, ticket, which):
        CreditDecision.objects.filter(ticket=ticket).update(**{
            'approver%d_comment' % which: 'Đồng ý với đề xuất của CED.'})

    def contract(self, ticket):
        """What CRA fills in to prepare the contract documents."""
        loan = LoanDetail.objects.get(ticket=ticket)
        scheme = loan.loan_pricing_scheme
        terms = LoanContract.objects.get(ticket=ticket)
        terms.loan_amount = terms.credit_limit = terms.disbursement_amount = loan.loanamount
        terms.interest_rate = str(scheme.promotion_rate if scheme else 9)
        terms.margin = str(scheme.margin if scheme else 2)
        terms.tenor, terms.purpose = loan.loan_tenor, loan.get_purpose_display()
        terms.disbursement_method = 'Chuyển khoản'
        terms.save()   # save(): fills the limit in words
        for collateral in CollaManager.objects.filter(ticket=ticket):
            CollateralContract.objects.update_or_create(collateral=collateral, defaults={
                'fulladdress': collateral.fulladdress_vn, 'land_area': collateral.land_area,
                'car_brand': collateral.car_brand, 'gcn_issue_place': 'Sở Tài nguyên và Môi trường (demo)',
                'dd_date': timezone.localdate()})
        CraDocInfo.objects.create(ticket=ticket, contract_type=1, contract_number='FA-%s' % ticket.title,
                                  sign_date=timezone.localdate(), signer='Nguyễn Văn An', position='Giám đốc (demo)')

    # ------------------------------------------------------------ workflow

    def pick_assignee(self, action, ticket, actor):
        choice = workflow.assignee_choices(action, ticket, actor)
        for holder in (ticket.ced, ticket.cra):
            if holder in choice.users:
                return holder
        return choice.suggested or (choice.users[0] if choice.users else None)

    def move(self, ticket, next_status):
        actor = ticket.assigned_to or ticket.submitter
        action = next((a for a in workflow.available_actions(actor, ticket) if a.next_status == next_status), None)
        if action is None:
            raise RuntimeError('No step from %s to %s for %s' % (ticket.status, next_status, actor))
        if ticket.status == Ticket.VERIFY_STATUS and next_status == Ticket.APPROVER1_STATUS:
            self.credit_review(ticket)
        if ticket.status in (Ticket.APPROVER1_STATUS, Ticket.APPROVER2_STATUS):
            self.approver_comment(ticket, 1 if ticket.status == Ticket.APPROVER1_STATUS else 2)
        if ticket.status == Ticket.DOCSPREP_STATUS:
            self.contract(ticket)
        reject_code = LOV.REJECT_CHOICES[0][0] if workflow.needs_reject_code(action, actor) else None
        comment = {Ticket.REJECT_STATUS: 'DSR vượt ngưỡng sau khi cộng các khoản vay hiện có.',
                   Ticket.SS_RQ_UPDATE: 'Bổ sung hợp đồng lao động của người vay chính.',
                   Ticket.CED_RQ_UPDATE: 'Bổ sung sao kê tài khoản 6 tháng.',
                   Ticket.CLOSED_STATUS: 'Khách hàng không tiếp tục vay.'}.get(next_status, '')
        return workflow.transition(ticket, action, actor, self.pick_assignee(action, ticket, actor), comment,
                                   reject_code=reject_code)


def backdate(ticket, days_ago):
    """Spread the application's history over the days since `days_ago`, like real work."""
    start = timezone.now() - datetime.timedelta(days=days_ago, hours=3)
    steps = list(FollowUp.objects.filter(ticket=ticket).order_by('id'))
    gap = datetime.timedelta(days=days_ago) / (len(steps) + 1)
    for index, followup in enumerate(steps, start=1):
        FollowUp.objects.filter(pk=followup.pk).update(date=start + gap * index)
    last = start + gap * len(steps)
    # Notifications of earlier steps are old news: dated with the last step and read,
    # except the one that handed an open application to its current handler.
    finished = ticket.status in workflow.FINISHED_STATUSES
    notes = Notification.objects.filter(ticket=ticket)
    notes.update(created=last, read_at=last)
    latest = notes.filter(user_id=ticket.assigned_to_id).order_by('-pk').first()
    if latest and not finished:
        notes.filter(pk=latest.pk).update(read_at=None)
    Ticket.objects.filter(pk=ticket.pk).update(
        created=start, modified=last, due_date=None if finished else last + datetime.timedelta(days=workflow.STEP_DAYS))


def disburse_completed(rng):
    """Completed applications were paid out by core banking: one or two disbursements each."""
    for ticket in Ticket.objects.filter(status=Ticket.COMPLETE_STATUS).select_related('contract'):
        amount = ticket.contract.disbursement_amount or 0
        if not amount:
            continue
        parts = [amount] if rng.random() < 0.6 else [amount * 6 // 10, amount - amount * 6 // 10]
        account = '1%011d' % rng.randint(0, 10 ** 11 - 1)
        when = ticket.modified - datetime.timedelta(days=len(parts))
        for index, part in enumerate(parts, start=1):
            Disbursement.objects.create(ticket=ticket, reference='CB-DEMO-%s-%d' % (ticket.title[-4:], index),
                                        amount=part, account_number=account,
                                        disbursed_at=when + datetime.timedelta(days=index - 1))


def returning_customer():
    """One customer with two loans: the borrower of a completed application applies again."""
    first = (Applicant.objects.filter(typeofapplicant=1, ticket__status=Ticket.COMPLETE_STATUS)
             .order_by('ticket__created').first())
    again = (Applicant.objects.filter(typeofapplicant=1, ticket__created__gt=first.ticket.created)
             .exclude(ticket__status__in=workflow.FINISHED_STATUSES).order_by('-ticket__created').first()
             if first else None)
    if again:
        Applicant.objects.filter(pk=again.pk).update(name_vn=first.name_vn, cid=first.cid, dob=first.dob,
                                                     gender=first.gender)


def seed(password, count=36, random_seed=2026):
    """Create the demo users and `count` applications spread over the workflow."""
    rng = random.Random(random_seed)
    if not Action.objects.exists():
        raise RuntimeError('No workflow steps; load the reference data first (loaddata demo_reference).')
    users = create_users(password)
    factory = ApplicationFactory(rng, users)
    sales = [users['sale1'], users['sale2']]
    for index in range(count):
        route = ROUTES[index % len(ROUTES)]
        with transaction.atomic():
            ticket = factory.build(sales[index % 2])
            for status in route:
                ticket = factory.move(ticket, status)
            if not route:
                # Still being entered by Sale: the income and collateral papers are not in yet.
                for document in AttachDocument.objects.filter(ticket=ticket, related_data__in=(3, 4)):
                    document.file.delete(save=False)
                    document.delete()
            backdate(ticket, days_ago=max(1, rng.randint(len(route), len(route) * 3 + 2)))
    disburse_completed(rng)
    returning_customer()
    return Seeded(users=len(users), applications=count)
