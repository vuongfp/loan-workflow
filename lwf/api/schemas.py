"""Request and response bodies of the API (OpenAPI schemas)."""
import datetime
from typing import Optional

from ninja import Field, Schema


class Problem(Schema):
    detail: str


# ------------------------------------------------------------ applications

class ApplicationSummary(Schema):
    number: str
    status_code: int
    status: str
    handler: Optional[str]
    product: Optional[str]
    loan_amount: Optional[int]
    tenor_months: Optional[int]
    created: datetime.datetime
    modified: datetime.datetime
    due: Optional[datetime.datetime]


class ApplicantOut(Schema):
    name: str
    role: str
    id_number: str = Field(description='Masked (079******426) unless the key may read personal data.')
    date_of_birth: Optional[datetime.date]
    monthly_income: int
    permanent_address: Optional[str]


class CollateralOut(Schema):
    type: Optional[str]
    value: Optional[int]
    address: Optional[str]


class AssessmentOut(Schema):
    monthly_income: Optional[int]
    existing_payments: Optional[int]
    dsr_highest: Optional[float]
    net_surplus: Optional[int]
    segment: Optional[str]
    crr_score: Optional[str]
    crr_band: Optional[str]


class DecisionOut(Schema):
    approved_amount: Optional[int]
    recommendation: Optional[str]


class ContractOut(Schema):
    loan_amount: Optional[int]
    credit_limit: Optional[int]
    disbursement_amount: Optional[int]
    interest_rate: Optional[str]
    margin: Optional[str]
    tenor_months: Optional[int]
    disbursement_method: Optional[str]


class PolicyBreachOut(Schema):
    rule: str
    actual: str
    limit: str
    deviation_code: int


class ApplicationDetail(ApplicationSummary):
    applicants: list[ApplicantOut]
    collaterals: list[CollateralOut]
    assessment: Optional[AssessmentOut]
    decision: Optional[DecisionOut]
    contract: Optional[ContractOut]
    missing_items: list[str] = Field(description='What Sale must still provide before sending it on.')
    policy_breaches: list[PolicyBreachOut]


class HistoryEntry(Schema):
    date: datetime.datetime
    by: Optional[str]
    step: Optional[str]
    new_status: Optional[str]
    comment: Optional[str]


# ------------------------------------------------------------ a customer's loans

class CustomerLookupIn(Schema):
    id_number: str = Field(min_length=6, max_length=20, description='CCCD / CMND / passport number of the customer.')


class CustomerOut(Schema):
    name: str
    id_number: str = Field(description='Masked unless the key may read personal data.')
    date_of_birth: Optional[datetime.date]


class DisbursementItem(Schema):
    reference: str
    amount: int
    disbursed_at: datetime.datetime
    account_number: str = Field(description='Only the last 4 digits unless the key may read personal data.')


class CustomerLoan(ApplicationSummary):
    stage: str = Field(description='in_progress, completed, rejected or closed')
    role: str = Field(description="The customer's role on the application (borrower, co-borrower ...)")
    approved_amount: Optional[int]
    contract: Optional[ContractOut]
    disbursed_amount: int
    disbursements: list[DisbursementItem]


class CustomerLoans(Schema):
    customer: CustomerOut
    applications: int
    in_progress: int
    approved_total: int
    disbursed_total: int
    loans: list[CustomerLoan]


class Product(Schema):
    product_code: int
    product: str
    subproduct_code: int
    subproduct: str


class Status(Schema):
    code: int
    name: str


# ------------------------------------------------------------ sign-in for apps

class TokenIn(Schema):
    username: str
    password: str
    device: str = ''


class TokenOut(Schema):
    token: str
    expires: datetime.datetime


class MeOut(Schema):
    username: str
    full_name: str
    groups: list[str]


# ------------------------------------------------------------ core banking

class ReadyForDisbursement(Schema):
    number: str
    borrower: Optional[str]
    borrower_id_number: Optional[str]
    disbursement_amount: Optional[int]
    already_disbursed: int
    interest_rate: Optional[str]
    tenor_months: Optional[int]
    disbursement_method: Optional[str]
    cra_officer: Optional[str]


class DisbursementIn(Schema):
    application: str = Field(description='Application number, e.g. DS.SS.26.0004')
    reference: str = Field(max_length=64, description='Core banking transaction reference; repeating it is harmless.')
    amount: int = Field(gt=0)
    disbursed_at: datetime.datetime
    account_number: str = Field(max_length=50)


class DisbursementOut(Schema):
    application: str
    reference: str
    amount: int
    disbursed_at: datetime.datetime
    account_number: str
    created: bool = Field(description='False when the reference had been received before.')


# ------------------------------------------------------------ credit bureau (CIC)

class SecuredLoanIn(Schema):
    original_amount: int
    interest_rate: float
    tenor_months: int
    outstanding: int
    progressive_disbursement: bool = False


class UnsecuredLoanIn(Schema):
    monthly_payments: list[int] = Field(description='Payments of the last three months.')


class OverdraftIn(Schema):
    interest_rate: float
    outstanding: int


class CreditCardIn(Schema):
    balances: list[int] = Field(description='Balances of the last six months.')


class CicReportIn(Schema):
    id_number: str
    report_date: datetime.date
    credit_group: str = Field('NoCIC', description='NoCIC, G1 ... G5')
    secured_loans: list[SecuredLoanIn] = []
    unsecured_loans: list[UnsecuredLoanIn] = []
    overdrafts: list[OverdraftIn] = []
    credit_cards: list[CreditCardIn] = []


class CicReportOut(Schema):
    applications_updated: list[str]


# ------------------------------------------------------------ eKYC

class EkycIn(Schema):
    application: str
    id_number: str
    full_name: str
    date_of_birth: Optional[datetime.date] = None
    gender: Optional[str] = None
    permanent_address: Optional[str] = None
    issue_date: Optional[datetime.date] = None
    issue_place: Optional[str] = None
    chip_verified: bool = False
    face_match_score: Optional[float] = Field(None, ge=0, le=100)


class EkycOut(Schema):
    passed: bool
    differences: list[str]
    applicant: str
