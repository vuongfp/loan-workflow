"""Loan application workflow: data model."""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from lwf import calculations, words

def upload_path(instance, filename):
    """Documents are stored per application: lwf/attachments/<application number>/<file>."""
    return 'lwf/attachments/%s/%s' % (instance.ticket.title if instance.ticket_id else 'unassigned', filename)


class Location(models.Model):
    code_ward = models.IntegerField(_('Ward Code'), blank=True, null=True)
    ward = models.CharField(_('Ward Name'), max_length=100, blank=True, null=True)
    level_ward = models.CharField(_('Ward Level'), max_length=100, blank=True, null=True)
    code_dist = models.IntegerField(_('District Cde'),  blank=True, null=True)
    dist = models.CharField(_('District Name'), max_length=100, blank=True, null=True)
    code_city = models.IntegerField(_('City Code'), blank=True, null=True)
    city = models.CharField(_('City Name'), max_length=100, blank=True, null=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Location'), _('Locations')

class LOV:
    """Choice lists used by the model fields (not a database table)."""
    RELATED_DATA_CHOICES =(
        (1,_('FUND USAGE PLAN/LOAN APPLICATION') ),
        (2,_('BORROWER/GAURANTOR INDENTIFICATION & CREDIT RECORD') ),
        (3,_('INCOME PROOF') ),
        (4,_('COLLATERAL& LOAN PURPOSE') ),
        (5,_('OTHERS DOCUMENTS') ),
        (6,_('SCREENING RESULT(All borrowers/Gaurantor)') ),    
        (7,_('VALUATION DOCUMENTS') ),  
    )
    DOCUMENT_TYPE_CHOICES=(
        (100,_('ID Card')),
        (101,_('Martial Status Proof')),
        (102,_('Family Book')),
    )
    CAPPING_CHOICES=(
        (1,_('Within')),
        (2,_('Exceeding')),
        (3,_('Not Applicable')),
    )

    EMPSTAT_CHOICES=(
        (0,_('Deactive')),
        (1,_('Active')),
        (2,_('Pending Approval')),
    )
    RESLOCATION_CHOICES = (
        (1, _('HCMC')),
        (2, _('Ha Noi 1')),
        (3, _('B. Duong (T. An)')),      
        (4, _('B. Duong (D. An)')),  
        (5, _('B. Duong (TDM)')),  
    )
    LOANPROGRAM_CHOICES = (
        (1, _('Not applicable')),
        (2, _('1A - Loan tenor')),
        (3, _('1B - MOA')),
        (4, _('1C - FHL')),
        (5, _('02 - DSR')),
        (6, _('Top up')),        
    )
    LAND_CHOICES = (
        (0,_('All')),
        (1,_('Land value only'))
    )
    DEVIATION_CHOICES  = (
        (101, _('101_Loan Tenure')),
        (102, _('102_Margin of Advance')),
        (103, _('103_Waiver of Formal Valuation by Panel Valuer (Mortgage)')),
        (104, _('104_Age Limit')),
        (105, _('105_Non-Target Property (eg. unqualified collateral requirement on minimum land area, land width, alley width, property location) / Fleet Purchase of Vehicles')),
        (106, _('106_Repayment conduct exceeded CIC credit guidelines (eg. Past record of G3+)')),
        (107, _('107_Exceeding Repayment Capability Indicators (eg. DSR / DSCR, NST, Gearing, Turnover, Negative net profit & tangible net worth in latest Tax Return Report)')),
        (108, _('108_High Risk Application (eg, Non-target business industry, Customer Segmentation Group III, Any borrower or guarantor with unsolved insolvency suits or legal action, Suspicious/fraud documents or verification failed)')),
        # (109, _('109_No longer in use')),
        (110, _('110_Loan amount')),
        (111, _('111_Waiver of Personal Guarantor (for Corporate Auto Loan)')),
        (112, _('112_Unqualified length in service/ working/ operation')),
    )
    COLLATERALTYPE_CHOICES = (
        (1, _('001 - TOWNHOUSE')),
        (3, _('003 - VACANT LAND')),
        (10, _('010 - IMPROVEMENT NOT YET UPDATED ON CO')),      
        (12, _('012 - APARTMENT')),  
    )
    CONSTRUCTIONSTATUS_CHOICES = (
        (1, _('Under construction')),
        (2, _('Completed')),
        (3, _('Completed (Not yet handover)')),                  
    )
    OCCUPATION_CHOICES = (
        (1, _('Owner occupied')),
        (2, _('Multiple tenants occupied')),
        (3, _('Single tenant occupied')),      
        (4, _('Third party occupied (non-tenancy)')),  
        (5, _('Un-occupied/ Empty house')),
        
    )
    BEDROOM_CHOICES = (
        (0, _('No. of Bedroom ≤ 6 ')),
        (1, _('No. of Bedroom >6')),
    )
    FINANCEPURPOSE_CHOICES = (
            (1,_('for residence')),
            (2,_('for residence & rent')),
            (3,_('for sales & rent')),
            (4,_('Domestic')),
            (5,_('Imported')),
    )
    PURPOSE_CHOICES  = (
            (0, _('-------------------')),
            (1, _('Purchase of Apartment')),
            (2,_('Purchase of Townhouse')),
            (3,_('Purchase of Residential land')), 
            (4,_('House renovation')),
            (5,_('Purchase of New car')),
            (6,_('Purchase of Used car')),
            (7,_('Purchase of household appliances/ interior/ consumption loan')),
            (8,_('Purchase of Land')),
        )

    ################################
    APPROVALTYPE_CHOICES = (
        (1, _('JDA')),
        (2, _('Exception')),
        (3, _('Normal')),
    )   
    GENDER_CHOICES = (
        (1, _('Male')),
        (2, _('Female')),
        # (3, _('Other')),
    )
    MARITAL_CHOICES = (
        (1, _('Married')),
        (2, _('Single')),
        (3, _('Separated/Divorced')),
        (4, _('Other')),
        (5, _('No information')),
    )
    EDU_CHOICES = (
        (1, _('Primary School')),
        (2, _('Secondary School')),
        (3, _('Graduate/equivalent')),
        (4, _('Post-graduate')),
        (5, _('No information')),        
    )
    NATIONALITY_CHOICES = (
        (1, _('Vietnamese')),
        (2, _('Non-Vietnamese (residing in VN >12M)')),
        (3, _('Non-Vietnamese')),      
    )
    BOOL_CHOICES = (
        (1, 'Yes'),
        (0, 'No'),        
    )
    RELATED_CHOICES = (
        (0, 'No'),
        (1, 'Yes'),        
    )
    RELATIONSHIP_CHOICES = (
        (0, 'New to Bank'),
        (1, 'Existing Borrower'),        
        (2, 'Previous Borrower'),        
        (3, 'Existing Applicant(Approved)'),        
    )
    INDUSTRY_CHOICES= (
        (1, _('Retail')),
        (2, _('Wholesale')),
        (3, _('Manufacturing')),
        (4, _('Service')),
        (5, _('Other')),
    )
    INDUSTRYDETAIL_CHOICES = (
        (101,1,_('Retail Others'),6.3),            					
        (102,1,_('Retail Textile & Apparel'),7.8),
        (103,1,_('Commerce Food & Beverage'),16.3),
        (104,1,_('Retail Transportation Equipment/Petrol Stations'),5.4),
        (105,1,_('Retail Furniture, Furnishing & Other Household Goods'),19.6),
        (106,1,_('Retail Hardware & Building Materials'),5.3),
        (107,1,_('Retail Computer & Office Equipment'),3.8),
        (108,1,_('Retail Supermarket, Dept Stores, Provision Shops'),4.6),
        (109,1,_('Retail Specific Commodities'),6.0),
        (201,2,_('Wholesale Others'),5.4),
        (202,2,_('Wholesale Transport Equipment'),6.4),
        (203,2,_('Wholesale Machines & Equipment'),7.2),
        (204,2,_('Wholesale Food, Drinks & Tobacco'),4.3),
        (205,2,_('Wholesale Timber, Paint & Construction Materials'),5.0),
        (206,2,_('Wholesale Textile & Apparel'),6.3),
        (207,2,_('Wholesale Scrap, Junk & Waste Dealers'),4.3),
        (208,2,_('Wholesale Industrial, Agri Machinery & Equipment'),7.3),
        (209,2,_('Wholesale Furniture, Furnishing & Other Household Goods'),5.9),
        (210,2,_('Wholesale Specific Commodities'),3.0),
        (211,2,_('Wholesale General Importers & Exporters'),8.0),
        (212,2,_('Wholesale Medical & Pharmaceutical Products'),8.4),
        (213,2,_('Wholesale Chemical & Chemical Products'),5.2),
        (214,2,_('Wholesale Paper, Cellophane Products & Stationery'),5.6),
        (301,3,_('Manufacturing Fabricated Metal Products'),9.4),
        (302,3,_('Manufacturing Chemicals'),9.4),
        (303,3,_('Manufacturing Paper'),12.4),
        (304,3,_('Manufacturing Wood'),7.6),
        (305,3,_('Manufacturing Textile, Apparel, Leather Products'),8.6),
        (306,3,_('Manufacturing Food, Beverage & Tobacco'),7.1),
        (307,3,_('Manufacturing Others'),8.1),
        (308,3,_('Manufacturing Non-Metallic Mineral Products - Petrol, Coal'),9.9),
        (309,3,_('Manufacturing Basic Metal Industries'),7.3),
        (401,4,_('Services Other Business Services'),20.2),
        (402,4,_('Services Personal and Household Services'),15.8),
        (403,4,_('Social Services & Leisure Services'),21.2),
        (404,4,_('Services Engineering, Architectural & Technical Svs'),12.9),
        (405,4,_('Services IT Professional'),16.4),
        (406,4,_('Services Holding & Investment Companies'),51.0),
        (407,4,_('Services Transport, Storage, Communicaton, Support'),14.7),
        (501,5,_('Construction Others'),8.3),
        (502,5,_('Construction General/Renovation Contractors'),6.8),
        (503,5,_('Mining & Quarrying'),11.6),
        (504,5,_('Agriculture Others'),12.6),
        (505,5,_('Electricity, Gas & water'),9.5),
    )
    HOUSEHOLD_INDUSTRY_CHOICES =  (
        # (1,_('Retailing of goods - Sundry / groceries/ suppliers - Food Industry (hawkers, bakeries, small restaurants)- Hardware, office equipment, etc'),10),
        # (2,_('Construction/ General Contractors '),10),
        # (3,_('Other Small Business '),10),
        # (4,_('Manufacturing '),15),
        # (5,_('Other Services Oriented Business- Advertising, consultants, repair workshops, hairdressing, cleaning etc.- Transportation'),15),
        # (6,_('Professionals, Service Firms/ Partnerships e.g. Accounting, Legal, Architect, Medical, Engineering etc (Professionals have very specialized skills and are known to have higher profit margins. Most of them are subjected to strict professional code of conduct of the respective professional bodies and maintain a sufficient payment conduct to avoid being from practice)'),20),
        (1,_('Retailing of goods'),10),
        (2,_('Construction/ General Contractors '),10),
        (3,_('Other Small Business '),10),
        (4,_('Manufacturing '),15),
        (5,_('Other Services Oriented Business'),15),
        (6,_('Professionals, Service Firms/ Partnerships'),20),

    )

    CONTRACTTYPE_CHOICES = (
        (1,_('Definite')),
        (2,_('Indefinite')),
    )

    PAYMENTTYPE_CHOICES = (
        (1,_('Bank transfer')),
        (2,_('In cash')),
        (3,_('Cash/Transfer')),
    )
    CONTRACTRENTAL_CHOICES = (
        (1,_('Notarized')),
        (2,_('Non-notarized')),
    )
    TYPEOFAPPLICANT_CHOICES = (
        (1, _('Primary Applicant')),
        (2, _('Co-applicant (Spouse)')),
        (3, _('Co-applicant (Parent)')),
        (4, _('Co-applicant (Sibling)')),
        (5, _('Guarantor (spouse)')),
    )

    TYPEOFHOUSE_CHOICES = (
        (1, _('Private House')),
        (2, _('Living with Parents')),
        (3, _('Co-owned')),
        (4, _('Rented House')),
        (5, _('Mortgaged House')),
        (6, _('Other')),
        (7, _('No information')),
    )

    RESIDENTIALSTATUS_CHOICES =(
        (1, _('Resident House')),
        (2, _('Non-resident')),
        (3, _('No information')),
    )
    REJECT_CHOICES = (
        (201,"Loan Tenure"),
        (202,"Margin Of Advance "),
        (203,"Fraud/Tampered Docs (Suspected) "),
        (204,"Age Limnit "),
        (205,"Non-Target/Unqualified Property "),
        (206,"Repayment conduct exceed CIC credit guilelines "),
        (207,"Exceeding DSR/DSCR/NST Guidelines "),
        (208,"Loan purpose is not eligible "),
        (209,"Others(i.e. Fail verification/negative infomation/employer disconected/unqualified policy "),
    )
    QC_CHOICES = (
        (1,"Identify"),
        (2,"LAF/Purpose"),
        (3,"Income.SAL"),
        (4,"Income.SEC"),
        (5,"Income.SHH"),
        (6,"Income.RTL"),
        (7,"Collateral"),
        (8,"CIC"),
        (9,"CRR"),
        (10,"AML"),
        (11,"Site Report"),
        (12,"Justification"),
        (13,"Info sufficiency"),
        (14,"Info accuracy"),
        (15,"Others"),
    )
    # WARD_CHOICES = ( (q[0], q[1]) for q in Location.objects.all().values_list('code_ward','ward').distinct() )
    # DIST_CHOICES = ( (q[0], q[1]) for q in Location.objects.all().values_list('code_dist','dist').distinct() )
    # CITY_CHOICES = ( (q[0], q[1]) for q in Location.objects.all().values_list('code_city','city').distinct() )

class PanelProject(models.Model):
    developer = models.CharField(
        _('Developer'),
        max_length = 50,
    )
    project = models.CharField(
        _('Project Name'),
        max_length = 200,
    ) 
    ldname  = models.CharField(
        _('LD Name'),
        max_length = 200,
    )
    dev_registered = models.CharField(
        _('Developper Name(Registered)'),
        max_length = 50,
        blank = True,
        null = True,
    )
    exp_date = models.DateField(
        _('Expire Date'),
        blank = True,
        null= True,
    )
    epmlimit = models.BigIntegerField(
        _('EPM Limit(VND mio)'),
        blank = True,
        null = True,
    )
    approvedloan = models.BigIntegerField(
        _('Approved Loan(VND mio)'),
        blank = True,
        null = True,
    )
    availablelimit = models.BigIntegerField(
        _('Available Limit (VND mio)'),
        blank = True,
        null = True,
    )

    status = models.IntegerField(
        _('Status'),
        choices= LOV.EMPSTAT_CHOICES,
        blank = True,
        null = True,
    )
    def __str__(self):
        return self.project

    class Meta:
        verbose_name, verbose_name_plural = _('Panel project'), _('Panel projects')

class LoanEarlyRepayment(models.Model):
    description= models.CharField(_("Description"),max_length=300, blank=True, null=True)
    early_rate1 = models.DecimalField(
        _('Early Rate(Year1)'),
        max_digits =10,
        decimal_places=3, blank=True, null=True
    )
    early_rate2 = models.DecimalField(
        _('Early Rate(Year2)'),
        max_digits =10,
        decimal_places=3, blank=True, null=True
    )
    early_rate3 = models.DecimalField(
        _('Early Rate(Year3)'),
        max_digits =10,
        decimal_places=3, blank=True, null=True
    )
    early_rate4 = models.DecimalField(
        _('Early Rate(Year4+)'),
        max_digits =10,
        decimal_places=3,  blank=True, null=True
    )
    
    def __str__(self):
        note = "Y1:" +  str(self.early_rate1) +"% - " + "Y2:" +  str(self.early_rate2) +"% - "+ "Y3:" +  str(self.early_rate3) +"% - ""Y4:" +  str(self.early_rate4) +"%"
        return note

    class Meta:
        verbose_name, verbose_name_plural = _('Early repayment fee'), _('Early repayment fees')
    
class CustomerType(models.Model):
    custype = models.CharField(
        _('Type'),
        max_length = 5,
    )
    name = models.CharField(
        _('Name'),
        max_length = 100,
    )
    def __str__(self):
        return self.custype + "::" + self.name

    class Meta:
        verbose_name, verbose_name_plural = _('Customer type'), _('Customer types')

class LoanScheme(models.Model):
    package = models.CharField(_('Package'), default='SS.PSL. ',max_length=100) 
    promotion_months = models.SmallIntegerField(_('Fixed Promotions Months'),default=2) 
    promotion_rate = models.DecimalField(_('Promotions Rate(% P.A)'),max_digits =10,decimal_places=3, default=0)
    prime = models.DecimalField(_('Prime Rate(% P.A)'),max_digits =10,decimal_places=3, default=0)
    margin = models.DecimalField(_('Normal Lending Margin(% P.A)'),max_digits =10,decimal_places=3)
    normal = models.DecimalField(_('Normal Lending Rate(% P.A)'),max_digits =10,decimal_places=3,default=0)
    early_payment =  models.ForeignKey(
        LoanEarlyRepayment,
        verbose_name=_('Early Payment Fee(%)'),
        on_delete= models.PROTECT,
        blank= True,
        null = True,
        )
    custype = models.ManyToManyField(
        CustomerType,
        verbose_name=_("Customer Type"),
    ) 
    minimum_loanamt = models.BigIntegerField(_('Minimum Loan Account'),blank=True,null=True,default=0)
    minimum_loantenor = models.SmallIntegerField(_('Minimum Loan Tenor'),blank=True,null=True,default=0)

    datefrom = models.DateField(_('Effective Date'))
    dateto = models.DateField(_('End Date'),blank=True, null=True,)
    description = models.CharField(_('Description'), max_length=200,default='None',blank=True, null=True,) 
    def __str__(self):
        pkg = self.package + ": Fixed in " + str(self.promotion_months) + " months "
        pkg = pkg + "- Promotion rate: " + str(self.promotion_rate) + "%"
        pkg = pkg + "- Normal rate: " + str(self.normal) + "%"
        return pkg

    def save(self, *args, **kwargs):        
        self.normal = self.prime + self.margin

        super(LoanScheme, self).save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Pricing scheme'), _('Pricing schemes')

class PanelCar(models.Model):
    brand = models.CharField(
        _('Car Brand'),
        max_length = 50,
    )
    dealer = models.CharField(
        _('Dealer Name'),
        max_length = 200,
    ) 
    ldname  = models.CharField(
        _('LD Name'),
        max_length = 200,
    )
    dealer_registered = models.CharField(
        _('Dealer Name(Registered)'),
        max_length = 50,
        blank = True,
        null = True,
    )
    exp_date = models.DateField(
        _('Expire Date'),
        blank = True,
        null= True,
    )
    epmlimit = models.BigIntegerField(
        _('EPM Limit(VND mio)'),
        blank = True,
        null = True,
    )
    approvedloan = models.BigIntegerField(
        _('Approved Loan(VND mio)'),
        blank = True,
        null = True,
    )
    availablelimit = models.BigIntegerField(
        _('Available Limit (VND mio)'),
        blank = True,
        null = True,
    )
    
    status = models.IntegerField(
        _('Status'),
        choices= LOV.EMPSTAT_CHOICES,
        blank = True,
        null = True,
    )
    def __str__(self):
        return str(self.id) + "::" + self.dealer

    class Meta:
        verbose_name, verbose_name_plural = _('Panel car dealer'), _('Panel car dealers')


class Product(models.Model):
    product_code = models.IntegerField(
        _('Product Code'),
        blank = True,
        null =True,
    )

    product = models.CharField(
        _('Product'),
        max_length=100,
    )
    ##################################
    subproduct_code = models.IntegerField(
        _('Sub-Product Code'),
        blank = True,
        null =True,
    )
    subproduct = models.CharField(
        _('Sub Product Code'),
        max_length=100,
        default=" "
    )
    crr_convert = models.CharField(
        _('CRR Convert'),
        max_length=100,
        default=" "
    )
    order = models.IntegerField(
        _('Index'),
        blank=True,null=True,
    )
    #################################
    def __str__(self):
        return self.product
    class Meta:
        verbose_name, verbose_name_plural = _('Product'), _('Products')
        ordering = ["order"]

class Ticket(models.Model):
    """A loan application: its status in the workflow and the people handling it."""

    OPEN_STATUS =11 # Full Input 
    ENDORSE_STATUS = 12 # Submit to SALEMNG 
    SUPPORT_STATUS = 13
    SS_RQ_UPDATE =19
    SD_APPROVE_EXCEPTION =14
    HS_APPROVE_EXCEPTION =16

    VERIFY_STATUS = 21
    CED_RQ_UPDATE = 29
    APPROVER1_STATUS = 22
    A1_RQ_UPDATE =24
    APPROVER2_STATUS = 23
    A2_RQ_UPDATE =25

    #for JDA
    CONCUR_STATUS =26

    POST_APPROVAL =27
    VALUATION_STATUS = 28 # chuyen cho SALE

    DOCSPREP_STATUS = 31
    CONFIRMFDISB_STATUS = 32
    CEDCHEKING_STATUS = 33
    CRA_RQ_UPDATE_STATUS = 39

    CEDCK_RQ_UPDATE = 35

    DISBURSEMENT_STATUS = 34
    
    COMPLETE_STATUS= 51
    REJECT_STATUS= 10
    CLOSED_STATUS = 50
    STATUS_CHOICES = (
        (OPEN_STATUS, _('Open')),
        (ENDORSE_STATUS, _('Sale Leader Endorse')), 
        (SUPPORT_STATUS, _('Sale Support Review')),
        (SS_RQ_UPDATE, _('Sale Support Request Update')),
        (SD_APPROVE_EXCEPTION, _('Head of Sale Approve Exception')),
        (HS_APPROVE_EXCEPTION, _('Head of PFS Approve Exception')),


        (VERIFY_STATUS, _('CED Verify Application')),
        (CED_RQ_UPDATE, _('CED Request Update')),
        
        (APPROVER1_STATUS, _('First Approval')),
        (A1_RQ_UPDATE, _('First Approver Request Update')),

        (APPROVER2_STATUS, _('Second Approval')),
        (A2_RQ_UPDATE, _(' Second Approver Request Update')),      

        (CONCUR_STATUS, _('Concurrence')),

        (POST_APPROVAL, _('Post Approval')),
        (VALUATION_STATUS, _('Request Valuation')),   
    
        (DOCSPREP_STATUS, _('CRA Prepare Document')),
        (CRA_RQ_UPDATE_STATUS, _('CRA Request Update')),

        (CONFIRMFDISB_STATUS , _('Sale Confirm Disbursement')),
        (CEDCHEKING_STATUS, _('CED Check Approval Condition')),
        (CEDCK_RQ_UPDATE, _('CED Request Update Pre Disbursement')),
        (DISBURSEMENT_STATUS, _('CRA Disbursement')),        
        
        (COMPLETE_STATUS, _('Complete')),
        (REJECT_STATUS, _('Reject')),
        (CLOSED_STATUS, _('Closed')),        
    )

    
    ##########################
    title = models.CharField(
        _('Title'),
        max_length=200,
        unique =True,
    ) # Application No.
    created = models.DateTimeField(
        _('Created'),
        blank=True,
    )

    modified = models.DateTimeField(
        _('Modified'),
        blank=True,
    )
    submitted = models.DateTimeField(
        _('Submitted'),
        blank=True,
        null=True,
        help_text=_('Date this ticket was submitted to CED'),
    )
    ###########Loan workflow######################
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitter',
        blank=True,
        null=True,
        verbose_name=_('Submitter'),
    )
    slead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='slead',
        blank=True,
        null=True,
        verbose_name=_('Sale Leader'),
    )
    ssupport = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ssupport',
        blank=True,
        null=True,
        verbose_name=_('Sale Support'),
    )
    sdirector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sdirector',
        blank=True,
        null=True,
        verbose_name=_('Sale Director'),
    )
    pfshead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pfshead',
        blank=True,
        null=True,
        verbose_name=_('Head of PFS'),
    )
    ced = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ced',
        blank=True,
        null=True,
        verbose_name=_('CED Officer'),
    )
    cra = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cra',
        blank=True,
        null=True,
        verbose_name=_('CRA Officer'),
    )
    approver1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approver1_tickets',
        blank=True,
        null=True,
        verbose_name=_('Approver 1 Officer'),
    )

    approver2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approver2_tickets',
        blank=True,
        null=True,
        verbose_name=_('Approver 2 Officer'),
    )

    apprtype = models.IntegerField(
        _('Approval Type'),
        choices=LOV.APPROVALTYPE_CHOICES,
        default=3,
        blank=True,
    )

    reject_code = models.SmallIntegerField(
        _('Reject Code (CED Onnly)'),
        choices=LOV.REJECT_CHOICES,
        blank=True,
        null=True,
    )

    amlscr = models.BooleanField(
        _('AML Screening '), blank=True,null=True, default=False
    )
    cpscr = models.BooleanField(
        _('Connected Parties (with Bank) '), blank=True,null=True, default=False
    )
    caplscr = models.BooleanField(
        _('Corp Auto Loan Watch List '), blank=True,null=True, default=False
    )
    ################################

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_to',
        blank=True,
        null=True,
        verbose_name=_('Assigned to'),
    )

    status = models.IntegerField(
        _('Status'),
        choices=STATUS_CHOICES,
        default=OPEN_STATUS,
    )

    description = models.TextField(
        _('Description'),
        blank=True,
        null=True,
    )

    due_date = models.DateTimeField(
        _('Due on'),
        blank=True,
        null=True,
    )

    class Meta:
        get_latest_by = "created"
        ordering = ('id',)
        verbose_name = _('Loan application')
        verbose_name_plural = _('Loan applications')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('admin:lwf_ticket_change', args=(self.id,))

    def save(self, *args, **kwargs):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = timezone.now()

        self.modified = timezone.now()

        super(Ticket, self).save(*args, **kwargs)

class Applicant(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete=models.CASCADE,blank=True,null=True)
    cid = models.CharField(_("Applicant ID"),max_length=12)
    
    permanent_address = models.CharField(_('Permanent address (unaccented)'),max_length=200, blank=True, null= True)
    permanent_address_vn = models.CharField(_('Permanent address'),max_length=200, blank=True, null= True)

    temporary_address = models.CharField(_('Current address (unaccented)'),max_length=200, blank=True, null= True)
    temporary_address_vn = models.CharField(_('Current address'),max_length=200, blank=True, null= True)
    
    name_vn = models.CharField(_("Applicant Name"),max_length=200)   
    name_en = models.CharField(_('Applicant Name'), max_length=200, blank=True,null= True,)

    typeofapplicant = models.IntegerField(_('Type of Applicant'),choices=LOV.TYPEOFAPPLICANT_CHOICES,default=1,)
    
    old_cid = models.CharField(_('Old ID'), max_length=50, blank=True, null= True)
    
    nationality = models.IntegerField(_('Nationality'), choices=LOV.NATIONALITY_CHOICES, default=1,)

    dob = models.DateField(_('Date of Birth'), blank=True, null= True,)
    age = models.IntegerField(_('Age'),blank=True,null=True)

    typehouse = models.IntegerField(_('Type of house for residential'),choices=LOV.TYPEOFHOUSE_CHOICES, default=1,blank=True,null= True)

    gender = models.IntegerField(_('Gender'), choices=LOV.GENDER_CHOICES, default=1,blank=True,null= True,)
    
    marital = models.IntegerField(_('Marital Status'), choices=LOV.MARITAL_CHOICES, default=1,blank=True,null= True,)
    
    edulvl = models.IntegerField(_("Education level"), choices=LOV.EDU_CHOICES ,blank=True, null=True)

    
    created = models.DateTimeField(
        _('Created'),
        blank=True,
        null=True,
    )

    modified = models.DateTimeField(
        _('Modified'),
        blank=True,
        null=True,
    )
    relatedparty = models.IntegerField(
        _("Related Party"), 
        choices = LOV.RELATED_CHOICES, 
        default=0,
        )
    relationship_bank = models.IntegerField(
        _("Relationship to Bank"), 
        choices = LOV.RELATIONSHIP_CHOICES, 
        default=0,
        )
    relatedparty_details = models.CharField(
        _('Related Party Details'), 
        max_length=200,
        
        blank=True,
        null= True,        
    )
    resstat  = models.IntegerField(_("Residential Status"), choices=LOV.RESIDENTIALSTATUS_CHOICES ,blank=True, null=True)
    
    reslocation = models.IntegerField(
        _('Residential Location'),
        choices=LOV.RESLOCATION_CHOICES,
        default=1,   
        blank=True,null= True,   
    )
    fix = models.BigIntegerField(_('Fixed Salary'), blank=True, null= True, default=0)
    var = models.BigIntegerField(_('Variable Salary'), blank=True, null= True, default=0)
    net = models.BigIntegerField(_('Salary Income'), blank=True, null= True, default=0)
    rental = models.BigIntegerField(_('Rental Income'), blank=True, null= True, default=0)
    business = models.BigIntegerField(_('Business Income'), blank=True, null= True, default=0)
    household = models.BigIntegerField(_('Household Income'), blank=True, null= True, default=0)
    total = models.BigIntegerField(_('Total Income'), blank=True, null= True, default=0)

    CIC5Y_CHOICES = (
        ('NoCIC', _('No CIC record')),         
        ('G1', _('Current G1, No past record of G2 or bad track record in last 5Y')),     
        ('G2', _('Current G1, Past record of G2 and No bad record in last 5Y')), 
        ('G3', _('Current G1, No past record of G2 or bad track record in last 5Y (min 01 year CIC vintage)')), 
        ('G4', _('Current G1 and Past bad track record in last 5Y')), 
        ('G5', _('Current G2 or above')), 
    )

    cicdate = models.DateField(_('CIC Report Date'), blank= True, null=True)
    cic5Y = models.CharField(_('Credit Record in last 5Y'),choices=CIC5Y_CHOICES, blank= True,null=True, max_length=10)
    total_outstanding = models.BigIntegerField(_('Total Outstanding Loan'),blank= True,null=True,default=0)
    creditcard = models.BigIntegerField(_('Credit Card Balance'),blank= True,null=True,default=0)

    highest_installment = models.BigIntegerField(_('Highest Installment'), blank= True,null=True,default=0)
    average_installment = models.BigIntegerField(_('Average Installment'), blank= True,null=True,default=0)

    #CRA Information
    cra_update = models.BooleanField(_("Update Status"),default=False, blank=True, null=True)
    cra_id_place = models.CharField(_('Nơi cấp CMND'),max_length=200, blank=True, null= True)
    cra_id_date = models.DateField(_(' Ngày cấp CMND'), blank=True, null= True)
    cra_permanent_address = models.CharField(_('Residential Address'),max_length=200, blank=True, null= True)
    cra_temporary_address = models.CharField(_('Current Address'),max_length=200, blank=True, null= True)

    description = models.TextField(_('Descriptions'),blank=True,null=True,)

    def save(self, *args, **kwargs):
        if self.dob:
            today = datetime.date.today()
            self.age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

        super(Applicant, self).save(*args, **kwargs)

        
    
    def __str__(self):
        return '%s (%s)' % (self.name_vn, self.cid)

    class Meta:
        verbose_name, verbose_name_plural = _('Applicant'), _('Applicants')
        constraints = [
            models.UniqueConstraint(fields=['ticket'], condition=models.Q(typeofapplicant=1),
                                    name='one_primary_applicant_per_ticket'),
        ]

class FollowUp(models.Model):
    """
    One entry in the history of an application: a status change, a re-assignment or a comment.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Ticket'),
    )

    date = models.DateTimeField(
        _('Date'),
        default=timezone.now
    )

    title = models.CharField(
        _('Title'),
        max_length=200,
        blank=True,
        null=True,
    )

    comment = models.TextField(
        _('Comment'),
        blank=True,
        null=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('User'),
    )

    new_status = models.IntegerField(
        _('New Status'),
        choices=Ticket.STATUS_CHOICES,
        blank=True,
        null=True,
        help_text=_('If the status was changed, what was it changed to?'),
    )

    class Meta:
        ordering = ('date',)
        verbose_name = _('Follow-up')
        verbose_name_plural = _('Follow-ups')

    def __str__(self):
        return '%s-%s' % (self.ticket.id, self.title)

    def save(self, *args, **kwargs):
        t = self.ticket
        t.modified = timezone.now()
        t.save()
        super(FollowUp, self).save(*args, **kwargs)

class TicketChange(models.Model):
    """
    For each FollowUp, any changes to the parent ticket (eg Title, Priority,
    etc) are tracked here for display purposes.
    """

    followup = models.ForeignKey(
        FollowUp,
        on_delete=models.CASCADE,
        verbose_name=_('Follow-up'),
    )

    field = models.CharField(
        _('Field'),
        max_length=100,
    )

    old_value = models.TextField(
        _('Old Value'),
        blank=True,
        null=True,
    )

    new_value = models.TextField(
        _('New Value'),
        blank=True,
        null=True,
    )

    def __str__(self):
        out = '%s ' % self.field
        if not self.new_value:
            out += gettext('removed')
        elif not self.old_value:
            out += gettext('set to %s') % self.new_value
        else:
            out += gettext('changed from "%(old_value)s" to "%(new_value)s"') % {
                'old_value': self.old_value,
                'new_value': self.new_value
            }
        return out

    class Meta:
        verbose_name = _('Ticket change')
        verbose_name_plural = _('Ticket changes')

# class UserSettings(models.Model):
#     """
#     A bunch of user-specific settings that we want to be able to define, such
#     as notification preferences and other things that should probably be
#     configurable.

#     We should always refer to user.usersettings_lwf.settings['setting_name'].
#     """

#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="usersettings_lwf")

#     settings_pickled = models.TextField(
#         _('Settings Dictionary'),
#         help_text=_('This is a base64-encoded representation of a pickled Python dictionary. '
#                     'Do not change this field via the admin.'),
#         blank=True,
#         null=True,
#     )

#     def _set_settings(self, data):
#         # data should always be a Python dictionary.
#         try:
#             import pickle
#         except ImportError:
#             import cPickle as pickle
#         from lwf.lib import b64encode
#         if six.PY2:
#             self.settings_pickled = b64encode(pickle.dumps(data))
#         else:
#             self.settings_pickled = b64encode(pickle.dumps(data)).decode()

#     def _get_settings(self):
#         # return a python dictionary representing the pickled data.
#         try:
#             import pickle
#         except ImportError:
#             import cPickle as pickle
#         from lwf.lib import b64decode
#         try:
#             if six.PY2:
#                 return pickle.loads(b64decode(str(self.settings_pickled)))
#             else:
#                 return pickle.loads(b64decode(self.settings_pickled.encode('utf-8')))
#         except pickle.UnpicklingError:
#             return {}

#     settings = property(_get_settings, _set_settings)

#     def __str__(self):
#         return 'Preferences for %s' % self.user

#     class Meta:
#         verbose_name = _('User Setting')
#         verbose_name_plural = _('User Settings')


# def create_usersettings(sender, instance, created, **kwargs):
#     """
#     Helper function to create UserSettings instances as
#     required, eg when we first create the UserSettings database
#     table via 'syncdb' or when we save a new user.

#     If we end up with users with no UserSettings, then we get horrible
#     'DoesNotExist: UserSettings matching query does not exist.' errors.
#     """
#     from lwf.settings import DEFAULT_USER_SETTINGS
#     if created:
#         UserSettings.objects.create(user=instance, settings=DEFAULT_USER_SETTINGS)


# models.signals.post_save.connect(create_usersettings, sender=settings.AUTH_USER_MODEL)



################

class Action(models.Model):    
       
    apprtype = models.SmallIntegerField(
        _("Approval Type"),
        choices = LOV.APPROVALTYPE_CHOICES
    )
    status = models.SmallIntegerField(
       _("Status"),
       choices = Ticket.STATUS_CHOICES 
    )
    team = models.ForeignKey(
        Group,
        on_delete = models.PROTECT,
        related_name = "current_team",
        verbose_name = "Current Team"
    )

    next_team = models.ForeignKey(
        Group,
        on_delete = models.PROTECT,
        related_name = "next_team",
        verbose_name = "Next Team"
    )
    next_status = models.SmallIntegerField(
       _("Next Status"),
       choices = Ticket.STATUS_CHOICES 
    )
    description = models.CharField(
        _("Description"),
        max_length =200
    )
    action_display = models.CharField(
        _("Action"),
        max_length =200,
        blank=True,null=True
    )
    def __str__(self):
        return "%s"%(self.description)

    class Meta:
        verbose_name, verbose_name_plural = _('Workflow action'), _('Workflow actions')

def product_choices():
    """(product_code, product) pairs from the Product table, read at call time."""
    return list(dict.fromkeys(Product.objects.values_list('product_code', 'product')))


def subproduct_choices():
    """(subproduct_code, subproduct) pairs from the Product table, read at call time."""
    return list(dict.fromkeys(Product.objects.values_list('subproduct_code', 'subproduct')))


class LoanDetail( models.Model):
    # product/subproduct hold codes from the Product table. They have no model
    # choices so that importing this module does not query the database; forms
    # load the choices when they are built.
    ticket = models.OneToOneField(
        Ticket,
        on_delete = models.CASCADE,
        related_name='loan',
        verbose_name = _('Ticket'),
    )
    product = models.IntegerField(
        _('Product'),
        blank=True,
        null=True,
    )
    subproduct = models.IntegerField(
        _('Sub-Product'),
        blank=True,
        null=True,
    )

    def get_product_display(self):
        return dict(product_choices()).get(self.product, self.product)

    def get_subproduct_display(self):
        return dict(subproduct_choices()).get(self.subproduct, self.subproduct)
    #######Loan workflow
    loanamount = models.BigIntegerField(
        _('Loan Amount'),
        blank=True,
        null=True,
        default=0,
    )
    purpose = models.IntegerField(
        _('Purpose'),
        choices=LOV.PURPOSE_CHOICES,
        default=0,
        blank=3,        
    )
    purposedetail = models.CharField(
        _('Loan Purpose Details[ For PSL Only] '),
        max_length=200,
        blank=True,
        null=True,
        default=" "

    )
    
    purposefinacing = models.IntegerField(
        _('Purpose of financing'),
        choices = LOV.FINANCEPURPOSE_CHOICES,
        blank=True,
        null= True,
    )
    purpose_details = models.CharField(
        _('Purpose details'), max_length=300, blank=True, null= True,        
    )
    
    loanprogram = models.IntegerField(
        _('Loan Program'),
        choices=LOV.LOANPROGRAM_CHOICES,
        default=1,
        blank=True, 
    )
    loan_pricing_scheme = models.ForeignKey(
        LoanScheme,
        on_delete = models.PROTECT,        
        verbose_name=_('Pricing Scheme'),
        blank=True,
        null =True         
    )
    loan_tenor = models.IntegerField(
        _('Tenor'),        
        default=0,
        blank=True,
        null =True 
    )
    loan_moa = models.SmallIntegerField(
        _('MOA (%)'), 
        blank=True, 
        null=True,  
        default= 0
        )

    loan_subject = models.CharField(
        _('Subject'), 
        max_length = 200,
        blank=True, 
        null=True,        
    )
    

    loan_land_value_only = models.IntegerField(_('Land value only'), choices=LOV.LAND_CHOICES, default=0,blank=True,null=True)
    
    deviation1 = models.IntegerField(
        _('Deviation (1)'),
        choices=LOV.DEVIATION_CHOICES,
        blank=True, null = True,        
    )

    deviation2 = models.IntegerField(
        _('Deviation (2)'),
        choices=LOV.DEVIATION_CHOICES,
        blank=True, null= True,        
    )
    deviation1_details = models.TextField(_('Deviation (1) reason'), blank=True, null=True)
    deviation2_details = models.TextField(_('Deviation (2) reason'), blank=True, null=True)
    sale_note = models.TextField(
        _('Sale Recommendation'),
        blank=True,
        null=True,
        default="Recommendations"
    )
    highest_installment = models.BigIntegerField(_('Loan Highest Installment'),default=0, blank=True, null=True)
    lowest_installment = models.BigIntegerField(_('Loan Lowest Installment'),default=0, blank=True, null=True)
    average_installment = models.BigIntegerField(_('Loan Average Installment'),default=0, blank=True, null=True)

    
    def __str__(self):
        return "%s"%(self.ticket.title)

    class Meta:
        verbose_name, verbose_name_plural = _('Loan request'), _('Loan requests')

class CollaManager(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete = models.CASCADE, verbose_name = _("Ticket"))
    colla_type = models.IntegerField(_('Collateral Type'),
                                        choices = ((1,_('Car')),(2,_('Mortgage Deed')),(3,_('Contract'))),
                                        blank=True,null= True,)
    existing_collateral  =  models.IntegerField(_('Existing Collateral'), choices = LOV.BOOL_CHOICES, blank=True,null= True, )   
    mortgage_type = models.IntegerField(_('Property Type'), choices = LOV.COLLATERALTYPE_CHOICES, blank=True, null= True,)
    title_deed = models.IntegerField(_('Title deed'),choices = LOV.BOOL_CHOICES,blank=True,default=1)
    address_available = models.IntegerField(_('Address Available'),choices = LOV.BOOL_CHOICES,blank=True,default=1)
    spa_or_estimated = models.BigIntegerField(_('SPA/ Estimated value'),default =0,blank=True,null=True)
    bedrooms = models.IntegerField(_('Number of Bedrooms'),choices = LOV.BEDROOM_CHOICES,default=1, blank=True, null= True)
    #Title Deed        
    land_plot = models.CharField( _('Land plot'), max_length=200, blank=True, null= True,)
    land_map = models.CharField( _('Land map'), max_length=200, blank=True, null= True,)
   
    fulladdress = models.CharField( _('Full Address'), max_length=200, blank=True, null= True,)
    fulladdress_vn = models.CharField( _('Full Address'), max_length=200, blank=True, null= True,)
    # street  = models.CharField( _('Unit - Address - Street'), max_length=200, blank=True, null= True,)
    # district =models.IntegerField(_('District'),choices =LOV.DIST_CHOICES,default = 760, blank=True,null= True,)
    # ward = models.IntegerField(_('Ward'),choices =LOV.WARD_CHOICES,default = 47507, blank=True,null= True,)
    # city = models.IntegerField(_('City/Province'),choices =LOV.CITY_CHOICES,default = 79, blank=True,null= True,)
   
    land_width = models.DecimalField(_('Land width(m)'), max_digits=10, decimal_places=3,blank=True,null=True, default=0)
    land_alley_width = models.DecimalField(_('Alley width(m)'), max_digits=10, decimal_places=3,blank=True,null= True, default=0)
    land_area = models.DecimalField(_('Land area/GFA (m2)'), max_digits=10,decimal_places=3,blank=True,null=True,default=0) 
    built_up_area = models.DecimalField(_('Built up area/NFA (m2)'), max_digits=10,decimal_places=3,blank=True,null=True,default=0) 
    construction_status = models.IntegerField(_('Construction status'),choices=LOV.CONSTRUCTIONSTATUS_CHOICES,blank=True,null= True,)

    occupancy = models.IntegerField(_('Property occupancy'),choices=LOV.OCCUPATION_CHOICES,blank=True,null= True,)
    # valuation_report = models.FileField(_('Valuation report'),upload_to=upload_path, blank=True,null=True)
    # valuation_report_filename = models.CharField(_('Filename'),max_length=1000,)
    # valuation_value = models.BigIntegerField(_('Valuation Value'), blank=True,null=True, default=0)
    # valuation_report_date = models.DateField(_('Date of Valuation report '),help_text=_('Date of Valuation report '),blank=True,null= True,)
    # contract
    
    
    project_name = models.ForeignKey(PanelProject,on_delete=models.PROTECT,verbose_name=_('Project Name'), blank=True,null= True,)
    project_dealer = models.CharField( _('Project Dealer'), max_length=200, blank=True, null= True,)
    project_developer = models.CharField( _('Project Developer'), max_length=200, blank=True, null= True,)

    # Use to check Limit
    mefstatus = models.CharField(_('EPM Status'), max_length=10,blank=True,null=True,default="No")
    mefexpdt = models.DateField(_('EPM Expire Date'),blank=True,null=True)
    mefavailm = models.CharField(_('EPM Limit Available'), max_length=10, blank=True,null=True)

    #########CAR#########
    car_brand = models.CharField(_('Brand of vehicle'),max_length=200,blank=True,null = True,)
    car_group = models.IntegerField(_('Vehicle Group Classification'),
                                    choices = ((1,_('Primary')),(2,_('Secondary'))),
                                    blank=True,null = True,default =1,)
    car_spa_value = models.BigIntegerField(_('SPA Value'),blank=True,null = True,default =0,)
    car_model = models.CharField(_('Model of vehicle (*)'),max_length=200,blank=True,null = True,)
    car_class = models.IntegerField(_('Vehicle Classification'),choices = ((1,_('Passenger')),(2,_('Pick-up'))),
                                        blank=True,null = True,default =1,)
    car_dealer =  models.ForeignKey(PanelCar,on_delete=models.PROTECT,verbose_name=_('Dealer Name'), blank=True,null= True,)
    car_dealer_other_name =  models.CharField(_('Other Dealer Name (*)'),max_length=200,blank=True,null = True,)
    car_year = models.IntegerField(_('Year of Manufacture'),blank=True,null = True)

    car_efstatus = models.CharField(_('EPM Status'), max_length=10,blank=True,null=True,default="No")
    car_efexpdt = models.DateField(_('EPM Expire Date'),blank=True,null=True)
    car_efavailm = models.CharField(_('EPM Limit Available'), max_length=10, blank=True,null=True)
    # def save(self, *args, **kwargs): 
    #     self.fulladdress = "%s %s %s %s" % ( self.street,self.get_ward_display(),
    #                                             self.get_district_display(),self.get_city_display())       
    #     super(CollaManager, self).save(*args, **kwargs)
        
    def __str__(self):
        return "%s"%(self.ticket.title)

    class Meta:
        verbose_name, verbose_name_plural = _('Collateral'), _('Collaterals')


class SalaryIncome(models.Model):
    ########Income#######################
    applicant = models.ForeignKey(
        Applicant,
        on_delete = models.CASCADE, 
        blank= True,
        null = True
    )
    employer  = models.CharField(
        _('Employer Name'),
        max_length=100,
        blank=True,
        null= True,
    )
    designation = models.CharField(
        _('Designation'),
        max_length=100,
        blank=True,
        null= True,)
    length_in_service = models.SmallIntegerField(
        _('Length in service (months)'),        
        blank=True,
        null= True,
    )
    CONTRACTTYPE_CHOICES = (
        (1,_('Definite')),
        (2,_('Indefinite')),
    )
    contract_type = models.IntegerField(
        _('Contract Type'),
        choices=LOV.CONTRACTTYPE_CHOICES,        
        blank=True,
        null= True,        
    )
    contract_date = models.DateField(
        _('Contract/Starting Date'),
        help_text=_('(Format: dd/mm/yyyy)'),
        blank=True,
        null= True,
    )

    previous_employer  = models.CharField(
        _('Previous Employer'),
        max_length=100,
        blank=True,
        null= True,
    )
    previous_length_in_service = models.SmallIntegerField(
        _('Previous Length in service (months)'),        
        blank=True,
        null= True,
    )


    contract_expdate = models.DateField(
        _('Expiry Date'),
        help_text=_('(Format: dd/mm/yyyy)'),
        blank=True,
        null= True,
    )

    payment_type =models.IntegerField(
        _('Payment Type'),
        choices= LOV.PAYMENTTYPE_CHOICES,
        default=1,
        blank=True,        
    )    

    monthamt = models.IntegerField(
        _('Number of Month'),
        choices=(
            (3,"3"),
            (6,"6"),
            (9,"9"),
            (12,"12"),
        ),
        blank=True,        
        default=6,
    )

    varmonthamt = models.IntegerField(
        _('Number of Month'),
        choices=(
            (3,"3"),
            (6,"6"),
            (9,"9"),
            (12,"12"),
        ),
        blank=True,        
        default=6,
    )

    fix_m1 = models.BigIntegerField(_('Month 1'), blank=True,null=True,default=0)
    fix_m2 = models.BigIntegerField(_('Month 2'), blank=True,null=True,default=0)
    fix_m3 = models.BigIntegerField(_('Month 3'), blank=True,null=True,default=0)
    fix_m4 = models.BigIntegerField(_('Month 4'), blank=True,null=True,default=0)
    fix_m5 = models.BigIntegerField(_('Month 5'), blank=True,null=True,default=0)
    fix_m6 = models.BigIntegerField(_('Month 6'), blank=True,null=True,default=0)
    fix_m7 = models.BigIntegerField(_('Month 7'), blank=True,null=True,default=0)
    fix_m8 = models.BigIntegerField(_('Month 8'), blank=True,null=True,default=0)
    fix_m9 = models.BigIntegerField(_('Month 9'), blank=True,null=True,default=0)
    fix_m10 = models.BigIntegerField(_('Month 10'), blank=True,null=True,default=0)
    fix_m11 = models.BigIntegerField(_('Month 11'), blank=True,null=True,default=0)
    fix_m12 = models.BigIntegerField(_('Month 12'), blank=True,null=True,default=0)
    fix_avg = models.BigIntegerField(_('Fixed Income'), blank=True,null=True,default=0)
    

    var_m1 = models.BigIntegerField(_('Month 1'), blank=True,null=True,default=0)
    var_m2 = models.BigIntegerField(_('Month 2'), blank=True,null=True,default=0)
    var_m3 = models.BigIntegerField(_('Month 3'), blank=True,null=True,default=0)
    var_m4 = models.BigIntegerField(_('Month 4'), blank=True,null=True,default=0)
    var_m5 = models.BigIntegerField(_('Month 5'), blank=True,null=True,default=0)
    var_m6 = models.BigIntegerField(_('Month 6'), blank=True,null=True,default=0)
    var_m7 = models.BigIntegerField(_('Month 7'), blank=True,null=True,default=0)
    var_m8 = models.BigIntegerField(_('Month 8'), blank=True,null=True,default=0)
    var_m9 = models.BigIntegerField(_('Month 9'), blank=True,null=True,default=0)
    var_m10 = models.BigIntegerField(_('Month 10'), blank=True,null=True,default=0)
    var_m11 = models.BigIntegerField(_('Month 11'), blank=True,null=True,default=0)
    var_m12 = models.BigIntegerField(_('Month 12'), blank=True,null=True,default=0)
    var_avg = models.BigIntegerField(_('Variable Income'), blank=True,null=True,default=0)

    avg = models.BigIntegerField(_('Net Income'), blank=True,null=True,default=0)

    def save(self, *args, **kwargs):
        calculations.salary(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Salary'), _('Salaries')
    ######################################
class HouseholdIncome(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    name = models.CharField(_('Business Name'), max_length=300, blank=True, null= True,)
    shareportion = models.DecimalField(_('Share portion(%)'), max_digits =10, decimal_places=3, blank=True,null=True,default=100)
    reg_no = models.CharField(_('Business Reg. No. '), max_length=300, blank=True, null= True,)
    reg_dt = models.DateField(_('Business Reg. Date'),blank=True,null=True)
    years = models.IntegerField(_('Years in business'), blank=True,null=True,default=0)

    char_capital = models.BigIntegerField(_('Chartered Capital (VND)'), blank=True,null=True,default=0)
    contributed = models.CharField(_('Contributed'), max_length=300, blank=True, null= True,)

    reg_address = models.CharField(_('Registered address'), max_length=300, blank=True, null= True,)
    years_at_address = models.IntegerField(_('Time stay at this address (years)'), blank=True, null= True,default=0)
    scope = models.CharField(_('Business scope'), max_length=300, blank=True, null= True,)

    HOUSEHOLD_INDUSTRY_CHOICES = ( (q[0],q[1]) for q in LOV.HOUSEHOLD_INDUSTRY_CHOICES)
    industry = models.IntegerField(_('Business Industry'), choices= HOUSEHOLD_INDUSTRY_CHOICES ,blank=True,null=True)

    typical_buyers = models.CharField(_('Typical buyers'), max_length=300, blank=True, null= True,)
    typical_suppliers = models.CharField(_('Typical suppliers'), max_length=300, blank=True, null= True,)
    
    # year1 = models.CharField(_('Year 1'), max_length=4, blank=True,null=True,default=2017)
    # year2 = models.CharField(_('Year 2'), max_length=4, blank=True,null=True,default=2018)
    # year3 = models.CharField(_('Year 3'), max_length=4, blank=True,null=True,default=2019)
    # year_compared = models.CharField(_('Sales Drop/Increase YoY '), max_length=300, blank=True, null= True,)

    # year1_sales_turnover = models.BigIntegerField(_('Sales Turnover 1'), blank=True,null=True,default=0)    
    # year1_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 1'), blank=True,null=True,default=0)   
    # year1_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    # year1_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)  
    # year1_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    # year1_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    # year1_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    

    # year2_sales_turnover = models.BigIntegerField(_('Sales Turnover 2'), blank=True,null=True,default=0)
    # year2_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 2'), blank=True,null=True,default=0)  
    # year2_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    # year2_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)
    # year2_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    # year2_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    # year2_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    

    # year3_sales_turnover = models.BigIntegerField(_('Sales Turnover 3'), blank=True,null=True,default=0)
    # year3_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 3'), blank=True,null=True,default=0)  
    # year3_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    # year3_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)
    # year3_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    # year3_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    # year3_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    
    
    # year_compared_sales_turnover = models.CharField(_('Sales Turnover'), max_length=50, blank=True,null=True,default=0) 
    # year_compared_net_profit = models.CharField(_('Net profit'), max_length=50, blank=True,null=True,default="Positive") 
     
    # year_compared_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    # year_compared_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    # year_compared_tangible_net_worth = models.CharField(_('Tangible net worth (>0)'),max_length=50, blank=True,null=True,default="Positive") 

    m1 = models.BigIntegerField(_('Month 1'), blank=True,null=True,default=0)
    m2 = models.BigIntegerField(_('Month 2'), blank=True,null=True,default=0)
    m3 = models.BigIntegerField(_('Month 3'), blank=True,null=True,default=0)
    m4 = models.BigIntegerField(_('Month 4'), blank=True,null=True,default=0)
    m5 = models.BigIntegerField(_('Month 5'), blank=True,null=True,default=0)
    m6 = models.BigIntegerField(_('Month 6'), blank=True,null=True,default=0)
    mamt = models.IntegerField(
        _('Number of Month'),
        choices=(
            (3,"3"),
            (6,"6"),
        ),
        blank=True,        
        default=3,
    )
    monthly_average = models.BigIntegerField(_('Monthly Average'), blank=True,null=True,default=0) 
    margin = models.DecimalField(_('Margin (%)'), max_digits =10, decimal_places=3, blank=True,null=True,default=0) 
    netincome = models.BigIntegerField(_('Net income (VND)'), blank=True,null=True,default=0)
    def __str__(self):
        return "%s"%self.name

    def save(self, *args, **kwargs):
        calculations.household(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Household business'), _('Household businesses')

class BusinessIncome(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    name = models.CharField(_('Business Name'), max_length=300, blank=True, null= True,)
    shareportion = models.DecimalField(_('Share portion(%)'), max_digits =10, decimal_places=3, blank=True,null=True,default=0)
    reg_no = models.CharField(_('Business Reg. No. '), max_length=300, blank=True, null= True,)
    reg_dt = models.DateField(_('Business Reg. Date'),blank=True,null=True)
    years = models.IntegerField(_('Years in business'), blank=True,null=True,default=0)

    char_capital = models.BigIntegerField(_('Chartered Capital (VND)'), blank=True,null=True,default=0)
    # paid_capital = models.BigIntegerField(_('Paid up capital (≥ VND 300 mio)'), blank=True,null=True,default=0)
    contributed = models.CharField(_('Contributed'), max_length=300, blank=True, null= True,)

    reg_address = models.CharField(_('Registered address'), max_length=300, blank=True, null= True,)
    ops_address = models.CharField(_('Main operating address'), max_length=300, blank=True, null= True,)
    scope = models.CharField(_('Business scope'), max_length=300, blank=True, null= True,)
    industry = models.IntegerField(_('Business Industry'), choices= LOV.INDUSTRY_CHOICES ,blank=True,null=True)

    INDUSTRYDETAIL_CHOICES = ( (q[0],q[2]) for q in LOV.INDUSTRYDETAIL_CHOICES)

    industrydetail = models.IntegerField(_('Business Industry Detail'), choices= INDUSTRYDETAIL_CHOICES ,blank=True,null=True)

    typical_buyers = models.CharField(_('Typical buyers'), max_length=300, blank=True, null= True,)
    typical_suppliers = models.CharField(_('Typical suppliers'), max_length=300, blank=True, null= True,)

    y1 = models.CharField(_('Year 1'), max_length=4, blank=True,null=True,default=2017)
    y2 = models.CharField(_('Year 2'), max_length=4, blank=True,null=True,default=2018)
    y3 = models.CharField(_('Year 3'), max_length=4, blank=True,null=True,default=2019)
    year_compared = models.CharField(_('Sales Drop/Increase YoY '), max_length=300, blank=True, null= True,)


    year1_sales_turnover = models.BigIntegerField(_('Sales Turnover 1'), blank=True,null=True,default=0)    
    year1_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 1'), blank=True,null=True,default=0)   
    year1_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    year1_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)  
    year1_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    year1_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    year1_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    

    year2_sales_turnover = models.BigIntegerField(_('Sales Turnover 2'), blank=True,null=True,default=0)
    year2_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 2'), blank=True,null=True,default=0)  
    year2_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    year2_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)
    year2_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    year2_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    year2_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    

    year3_sales_turnover = models.BigIntegerField(_('Sales Turnover 3'), blank=True,null=True,default=0)
    year3_net_sales_turnover= models.BigIntegerField(_('Net Monthly Average Turnover 3'), blank=True,null=True,default=0)  
    year3_net_profit = models.BigIntegerField(_('Net profit'), blank=True,null=True,default=0)  
    year3_paidup_capital = models.BigIntegerField(_('Paid-up Capital'), blank=True,null=True,default=0)
    year3_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    year3_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    year3_tangible_net_worth = models.BigIntegerField(_('Tangible net worth (>0)'), blank=True,null=True,default=0)    
    
    year_compared_sales_turnover = models.CharField(_('Sales Turnover'), max_length=50, blank=True,null=True,default=0) 
    year_compared_net_profit = models.CharField(_('Net profit'), max_length=50, blank=True,null=True,default="Positive") 
     
    year_compared_retained_earning  = models.BigIntegerField(_('Retained Earning'), blank=True,null=True,default=0)   
    year_compared_intangible_assets = models.BigIntegerField(_('Intangible assets'), blank=True,null=True,default=0)    
    year_compared_tangible_net_worth = models.CharField(_('Tangible net worth (>0)'),max_length=50, blank=True,null=True,default="Positive") 

    vat_period  = models.IntegerField(
        _('Period'),
        choices=(
            (6,"6M"),
            (9,"9M"),
            (12,"12M"),
        ),
        blank=True,        
        default=6,
    )    
    bank_statement_period = models.IntegerField(_('Bank statement'), blank=True,null=True,default=0) 
    vat_amount = models.BigIntegerField(_('VAT Declaration'), blank=True,null=True,default=0)  
    bank_statement_amount = models.BigIntegerField(_('Bank statement'), blank=True,null=True,default=0)
    vat_monthly = models.BigIntegerField(_('VAT Declaration'), blank=True,null=True,default=0)
    bank_statement_monthly = models.BigIntegerField(_('Bank statement'), blank=True,null=True,default=0)
    
    monthly_average = models.BigIntegerField(_('Monthly Average'), blank=True,null=True,default=0) 
    EBITDAmargin = models.DecimalField(_('EBITDA Margin (%)'), max_digits =10, decimal_places=3, blank=True,null=True,default=0) 
    netincome = models.BigIntegerField(_('Net income (VND)'), blank=True,null=True,default=0) 
    def __str__(self):
        return "%s"%self.name

    def save(self, *args, **kwargs):
        calculations.business(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Business'), _('Businesses')

class RentalIncome(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    address = models.CharField(_('Property address'), max_length=300, blank=True, null= True,) 
    leasing_price= models.BigIntegerField(_('Leasing price (VND)'), blank=True,null=True,default=0)  
    contract_type = models.BigIntegerField(_('Contract type'), choices= LOV.CONTRACTRENTAL_CHOICES, blank=True,null=True,default=0) 
    proxy_margin= models.BigIntegerField(_('Proxy margin (%)'), blank=True,null=True,default=90)  
    payment_type= models.IntegerField(_('Payment type'), choices= LOV.PAYMENTTYPE_CHOICES ,blank=True,null=True,default=1) 
    mortgage_status= models.IntegerField(_('Mortgage status'), choices= LOV.BOOL_CHOICES ,blank=True,null=True,default=0)  
    net_income= models.BigIntegerField(_('Net rental income'), blank=True,null=True,default=0)  

    def save(self, *args, **kwargs):
        calculations.rental(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Rental income'), _('Rental incomes')


class CreditDecision(models.Model):
    """The credit assessment's decision on an application (CED and approvers)."""
    ticket = models.OneToOneField('Ticket', on_delete=models.CASCADE, related_name='decision',
                                  verbose_name=_('Application'))
    approved_amount = models.BigIntegerField(_('Approval Limit'), blank=True, null=True, default=0)
    desktop_valuation = models.BigIntegerField(_("Desktop Valuation(VND)"), blank=True, null=True, default=0)
    report_valuation = models.BigIntegerField(_("Valuation Report(VND)"), blank=True, null=True, default=0)
    variance = models.CharField(_("Variance"), max_length=5, blank=True, null=True)
    covid_affected = models.IntegerField(_('New COVID 19 affected'), choices=LOV.BOOL_CHOICES, blank=True, null=True)
    portfolio_capping = models.IntegerField(_('Portfolio capping limit'), choices=LOV.CAPPING_CHOICES, blank=True, null=True)
    recommendation = models.TextField(_('CED Recommendation'), blank=True, null=True)
    approver1_comment = models.TextField(_("Approver1's comment"), blank=True, null=True)
    approver2_comment = models.TextField(_("Approver2's comment"), blank=True, null=True)
    error_codes = models.CharField(_("Error Codes"), max_length=200, blank=True, null=True)
    values_report = models.FileField(_("Values Report"), upload_to=upload_path, max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name = _('Credit decision')

    def __str__(self):
        return str(self.ticket)


class LoanContract(models.Model):
    """Terms written into the credit contract (CRA)."""
    ticket = models.OneToOneField('Ticket', on_delete=models.CASCADE, related_name='contract',
                                  verbose_name=_('Application'))
    loan_amount = models.BigIntegerField(_('Số tiền đề nghị'), blank=True, null=True, default=0)
    credit_limit = models.BigIntegerField(_('Hạn Mức Tín dụng'), blank=True, null=True, default=0)
    credit_limit_in_words = models.CharField(_('Bằng chữ:'), max_length=200, blank=True, null=True)
    disbursement_amount = models.BigIntegerField(_('Số tiền giải ngân'), blank=True, null=True, default=0)
    interest_rate = models.CharField(_('Lãi suất'), max_length=6, blank=True, null=True)
    margin = models.CharField(_('Biên độ'), max_length=6, blank=True, null=True)
    early_repayment_fee = models.CharField(_('Phí trả trươc hạn'), max_length=200, blank=True, null=True)
    purpose = models.CharField(_('Mục đích'), max_length=100, blank=True, null=True)
    disbursement_method = models.CharField(_('Phương thức giải ngân'), max_length=100, blank=True, null=True)
    tenor = models.IntegerField(_('Tenor'), default=0, blank=True, null=True)
    conditions = models.TextField(_('Đk/Đk khác'), blank=True, null=True, default="")

    class Meta:
        verbose_name = _('Loan contract')

    def __str__(self):
        return str(self.ticket)

    def save(self, *args, **kwargs):
        # The contract writes the limit in words too; it follows the figure.
        self.credit_limit_in_words = words.amount_words(self.credit_limit) if self.credit_limit else ''
        super().save(*args, **kwargs)


class CollateralContract(models.Model):
    """Legal details of one collateral for the mortgage contract (CRA)."""
    collateral = models.OneToOneField('CollaManager', on_delete=models.CASCADE, related_name='contract',
                                      verbose_name=_('Collateral'))
    GCN_CHOICES = (('GCN01', 'Giấy chứng nhận quyền sử dụng đất'), ('GCN02', 'Giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà và tài sản khác gắn liền với đất'), ('GCN03', 'Giấy chứng nhận quyền sở hữu nhà ở và quyền sử dụng đất'))
    COLLA_CHOICES = (('COLL01', 'Căn hộ'), ('COLL02', 'Quyền sử dụng đất'), ('COLL03', 'Quyền sử dụng đất, quyền sở hữu nhà và tài sản khác gắn liền với đất'), ('COLL04', 'Quyền sở hữu nhà ở và quyền sử dụng đất ở'))
    car_brand = models.CharField(_('Nhãn hiệu xe'), max_length=200, blank=True, null=True)
    car_body_no = models.CharField(_('Số khung'), max_length=200, blank=True, null=True)
    car_machine_no = models.CharField(_('Số máy'), max_length=200, blank=True, null=True)
    car_dealer = models.CharField(_('Tên Đại lý bán xe'), max_length=200, blank=True, null=True)
    car_spa_value = models.CharField(_('Giá trị xe (theo hóa đơn) (bằng số)'), max_length=200, blank=True, null=True)
    car_spa_value_inwords = models.CharField(_('Giá trị xe (theo hóa đơn) (bằng chữ)'), max_length=200, blank=True, null=True)
    land_plot = models.CharField(_('Land plot'), max_length=200, blank=True, null=True)
    land_map = models.CharField(_('Land map'), max_length=200, blank=True, null=True)
    land_area = models.CharField(_('Land area/GFA (m2)'), max_length=200, blank=True, null=True)
    built_up_area = models.CharField(_('Built up area/NFA (m2)'), max_length=200, blank=True, null=True)
    fulladdress = models.CharField(_('Full Address'), max_length=200, blank=True, null=True)
    land_using_type = models.CharField(_('Hình thức sử dụng'), max_length=200, blank=True, null=True)
    land_using_purpose = models.CharField(_('Mục đích sử dụng'), max_length=200, blank=True, null=True)
    land_using_time = models.CharField(_('Thời hạn sử dụng'), max_length=200, blank=True, null=True)
    land_using_source = models.CharField(_('Nguồn gốc sử dụng'), max_length=200, blank=True, null=True)
    house_structure = models.CharField(_('Kết cấu nhà'), max_length=200, blank=True, null=True)
    house_level = models.CharField(_('Cấp (Hạng)'), max_length=200, blank=True, null=True)
    house_numfloor = models.IntegerField(_('Số tầng'), blank=True, null=True, default=1)
    house_built_year = models.CharField(_('Năm hoàn thành xây dựng'), max_length=200, blank=True, null=True)
    house_using_time = models.IntegerField(_('Thời hạn sở hữu'), blank=True, null=True, default=10)
    investor = models.CharField(_('Tên Chủ Đầu Tư'), max_length=200, blank=True, null=True)
    apartment_code = models.CharField(_('Mã căn hộ'), max_length=200, blank=True, null=True)
    floor_number = models.CharField(_('Tầng số'), max_length=3, blank=True, null=True)
    contract_no = models.CharField(_('Số Hợp Đồng Mua Bán'), max_length=50, blank=True, null=True)
    contract_date = models.DateField(_('Ngày ký Hợp Đồng Mua Bán'), blank=True, null=True)
    contract_value = models.BigIntegerField(_('Giá trị theo Hợp Đồng Mua Bán'), blank=True, null=True, default=0)
    house_built_up_area = models.CharField(_('Diện tích xây dựng (m2)'), max_length=200, blank=True, null=True)
    house_using_area = models.CharField(_('Diện tích sàn/Diện tích sử dụng (m2)'), max_length=200, blank=True, null=True)
    area_inwords = models.CharField(_('Diện tích bằng chữ'), max_length=200, blank=True, null=True)
    house_using_area_inwords = models.CharField(_('Diện tích sử dụng bằng chữ'), max_length=200, blank=True, null=True)
    floor_area = models.CharField(_('Diện tích sàn (m2)'), max_length=200, blank=True, null=True)
    area = models.CharField(_('Diện tích sàn/Diện tích sử dụng (m2)'), max_length=200, blank=True, null=True)
    gcn_name = models.CharField(_('Tên giấy chứng nhận'), choices=GCN_CHOICES, max_length=200, blank=True, null=True)
    total_value_dd = models.CharField(_('Giá trị định giá tổng (bắng số và bằng chữ)'), max_length=200, blank=True, null=True)
    colla_name = models.CharField(_('Tên loại tài sản đảm bảo (trên FA, BBDG và GUQ)'), choices=COLLA_CHOICES, max_length=200, blank=True, null=True)
    land_dd_value = models.CharField(_('Giá trị định giá đất (bắng số và bằng chữ)'), max_length=200, blank=True, null=True)
    issue_no = models.CharField(_('Số phát hành GCN'), max_length=200, blank=True, null=True)
    builtup_value = models.CharField(_('Giá trị định giá phần xây dựng (bắng số và bằng chữ)'), max_length=200, blank=True, null=True)
    paper_issue_no = models.CharField(_('Số vào sổ cấp GCN/Hồ sơ gốc số'), max_length=200, blank=True, null=True)
    dd_date = models.DateField(_('Ngày định giá'), blank=True, null=True)
    gcn_issue_date = models.DateField(_('Ngày cấp GCN'), blank=True, null=True)
    gcn_issue_place = models.CharField(_('Nơi cấp GCN'), max_length=200, blank=True, null=True)
    value_dd = models.CharField(_('Tên chi nhánh văn phòng đăng ký đất đai nơi có tài sản'), max_length=200, blank=True, null=True)
    notarize_contract_name = models.CharField(_('Tên Hợp Đồng Mua Bán công chứng'), max_length=200, blank=True, null=True)
    notarize_contract_no = models.CharField(_('Số công chứng của Hợp Đồng chuyển nhượng'), max_length=50, blank=True, null=True)
    notarize_contract_date = models.DateField(_('Ngày công chứng Hợp Đồng chuyển nhượng'), blank=True, null=True)
    notarize_department_name = models.CharField(_('Tên phòng công chứng thực hiện công chứng Hợp Đồng chuyển nhượng'), max_length=200, blank=True, null=True)
    notarize_transfer_no = models.CharField(_('Số xác nhận chuyển nhượng của Chủ Đầu Tư'), max_length=50, blank=True, null=True)
    notarize_transfer_date = models.DateField(_('Ngày ký của Xác Nhận Chuyển Nhượng của Chủ Đầu Tư'), blank=True, null=True)
    mortgage_description = models.TextField(_('Ghi chú'), blank=True, null=True)

    class Meta:
        verbose_name = _('Collateral contract data')

    def __str__(self):
        return str(self.collateral)

    def save(self, *args, **kwargs):
        # Values the contracts also write in words, kept in step with the figures.
        self.car_spa_value_inwords = words.amount_words(self.car_spa_value)
        self.area_inwords = words.amount_words(self.area, 'mét vuông')
        self.house_using_area_inwords = words.amount_words(self.house_using_area, 'mét vuông')
        super().save(*args, **kwargs)


class CicSecureLoan(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    original_amount = models.BigIntegerField(_('Original amount(VND)'),blank =True, null=True,default=0)
    interest_rate =  models.DecimalField(_('Interest rate(%)'), max_digits =10, decimal_places=3,blank =True, null=True,default=0)
    loan_tenor = models.SmallIntegerField(_('Loan tenor(months)'),blank =True, null=True,default=0)
    outstanding_loan= models.BigIntegerField(_('Outstanding Loan(VND) '),blank =True, null=True,default=0)
    progressive_disbursement= models.BooleanField(_('Progressive Disbursement '),blank =True, null=True,default=0)
    highest_installment 	= models.BigIntegerField(_('Highest Installment(VND) '),blank =True, null=True,default=0)
    averageinstallment= models.BigIntegerField(_('Average Installment(VND) '),blank =True, null=True,default=0)

    def save(self, *args, **kwargs):
        calculations.secured_loan(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Secured loan (CIC)'), _('Secured loans (CIC)')

class CicUnSecureLoan(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    m1 = models.BigIntegerField(_('Month 1 '),blank =True, null=True,default=0)
    m2 = models.BigIntegerField(_('Month 2 '),blank =True, null=True,default=0)
    m3 = models.BigIntegerField(_('Month 3 '),blank =True, null=True,default=0)
    installment = models.BigIntegerField(_('Highest/Average Installment '),blank =True, null=True,default=0)

    def save(self, *args, **kwargs):
        calculations.unsecured_loan(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Unsecured loan (CIC)'), _('Unsecured loans (CIC)')

class CicOverDraft(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    interest_rate =  models.DecimalField(_('Interest rate(%) '), max_digits =10, decimal_places=3,blank =True, null=True,default=0)
    outstanding_loan= models.BigIntegerField(_('Outstanding Loan '),blank =True, null=True,default=0)
    installment 	= models.BigIntegerField(_('Highest/Average Installment '),blank =True, null=True,default=0)

    def save(self, *args, **kwargs):
        calculations.overdraft(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Overdraft (CIC)'), _('Overdrafts (CIC)')

class CicCreditCard(models.Model):
    applicant = models.ForeignKey(Applicant,on_delete = models.CASCADE, blank= True,null = True)
    bm1 = models.BigIntegerField(_('Month 1 '),blank =True, null=True,default=0)
    bm2 = models.BigIntegerField(_('Month 2 '),blank =True, null=True,default=0)
    bm3 = models.BigIntegerField(_('Month 3 '),blank =True, null=True,default=0)
    bm4 = models.BigIntegerField(_('Month 4 '),blank =True, null=True,default=0)
    bm5 = models.BigIntegerField(_('Month 5 '),blank =True, null=True,default=0)
    bm6 = models.BigIntegerField(_('Month 6 '),blank =True, null=True,default=0)
    avg_balance_6m= models.BigIntegerField(_('Avg. card balance in last 6M '),blank =True, null=True,default=0)
    proxy_min_pay= models.BigIntegerField(_('Proxy min payment'),blank =True, null=True,default=5)
    highest_installment 	= models.BigIntegerField(_('Installment(Highest)'),blank =True, null=True,default=0)
    averageinstallment= models.BigIntegerField(_('Installment(Avg)'),blank =True, null=True,default=0)

    def save(self, *args, **kwargs):
        calculations.credit_card(self)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name, verbose_name_plural = _('Credit card (CIC)'), _('Credit cards (CIC)')

class Condition(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete = models.CASCADE)
    CONDITION_TYPES=(
        (1,_('Pre-disbursement')),
        (2,_('Post-disbursement')),
        (3,_('Accept Pending Dox')),
    )
    # DETAIL_CHOICES = (
    #     ("Detail_1",_('Terms & conditions as per respective Project Empanelment Approval [CRA]')),
    #     ("Detail_1",_('Subject to (i) valid Car Dealer Empanelment; AML annual review & respective Cooperation contract, or (ii) submission of original Vehicle Registration Certificate [CRA]”, else show “Subject to submission of original Vehicle Registration Certificate [CRA]')),
    #     ("Detail_1",_('Subject to required documents for the above mentioned loan purpose as per approved policy/SOP [CRA]')), 
    #     ("Detail_1",_('Subject to (i) standard requirement on collateral as per approved policy [CED] and (ii) required document for the above mentioned loan purpose as per approved policy/SOP [CRA]')), 
    #     ("Detail_1",_('Subject to the checking requirement as per approved policy/SOP [CRA/PFS]')), 
    #     ("Detail_1",_('Subject to standard requirement on collateral as per approved policy [CED]')), 
    # )RELATED_DATA_CHOICES
    condition_type = models.IntegerField(_("Condition Type"), choices=CONDITION_TYPES, blank=True, null=True)
    condition_detail = models.TextField(_("Condition Details"), blank=True, null=True, default="-")
    dox_type= models.IntegerField(_("Document Type"), choices=LOV.RELATED_DATA_CHOICES, blank=True, null=True)
    followbyced_status= models.BooleanField(_("Follow by CED"),blank=True, null=True,default=False)
    followbycra_status= models.BooleanField(_("Follow by CRA"),blank=True, null=True,default=False)
    def __str__(self):
        return "%s"%self.ticket.title

    class Meta:
        verbose_name, verbose_name_plural = _('Condition'), _('Conditions')



class CraDocInfo(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete = models.CASCADE)
    CRA_DOC_TYPES = (
        (1,_('Số Hợp Đồng Tín Dụng (FA)')),
        (2,_('Hợp Đồng Thế Chấp (MA)')),
        (3,_('Hợp Đồng Ba Bên(TA)')),
        (4,_('Biên Bản Định Giá(BBDG)')),
    )
    contract_type = models.IntegerField(
        _('Loại Hợp đồng'),
        choices= CRA_DOC_TYPES,
        blank=True,
        null=True,
    )
    
    contract_number = models.CharField(
        _('Số Hợp đồng'),
        max_length=100, 
        blank=True,
        null=True,
    )

    sign_date = models.DateField(
        _('Ngày ký'),
        blank=True,
        null=True,
    )
    signer = models.CharField(
        _('Người ký'),
        max_length=100, 
        blank=True,
        null=True,
    )
    position = models.CharField(
        _('Chức vụ'),
        max_length=100, 
        blank=True,
        null=True,
    )
    saler1 = models.CharField(
        _('Họ và tên của người bán thứ 1'),
        max_length=100, 
        blank=True,
        null=True,
    )
    saler2 = models.CharField(
        _('Họ và tên của người bán thứ 2'),
        max_length=100, 
        blank=True,
        null=True,
    )
    def __str__(self):
        return "%s"%self.contract_number

    class Meta:
        verbose_name, verbose_name_plural = _('Contract document'), _('Contract documents')

class AttachDocument(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete = models.CASCADE, blank=True,null = True)
    related_data = models.IntegerField(
        _("Related Data"),
        choices = LOV.RELATED_DATA_CHOICES,
        blank=True,null=True,        
    )
    file = models.FileField(upload_to=upload_path)
    filename = models.CharField(
        _('Filename'),
        max_length=1000,blank=True,null=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return "%s-%s"%(self.related_data, self.filename)

    class Meta:
        verbose_name, verbose_name_plural = _('Document'), _('Documents')
    
class Officer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='officer')
    product = models.ForeignKey(Product, on_delete = models.SET_NULL, null=True)    
    mainteam = models.ForeignKey( Group,on_delete = models.SET_NULL,null=True)
    created = models.DateTimeField(_("Add"),auto_now_add=True)
    modified = models.DateTimeField(_("Update"), blank=True, null=True)
    available = models.BooleanField(_("Available"),default=True)
    def save(self, *args, **kwargs):
        self.modified = timezone.now()
        super(Officer,self).save(*args, **kwargs)

    def __str__(self):
        return "%s-%s-%s-%s"%(self.mainteam, self.product, self.user, self.available)

    class Meta:
        verbose_name, verbose_name_plural = _('Officer'), _('Officers')

class ScoreMatrixVersion(models.Model):
    """
    A version of the CRR score matrix. One version is active and scores new
    applications; each score records the version it used, and a version that
    has scored applications can no longer be edited, so old scores stay explainable.
    """
    name = models.CharField(_('Version'), max_length=50, unique=True)
    effective_from = models.DateField(_('Effective from'), default=timezone.localdate)
    note = models.TextField(_('Note'), blank=True)
    is_active = models.BooleanField(_('Active'), default=False)
    created = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Score matrix version'), _('Score matrix versions')
        ordering = ('-effective_from', '-pk')
        constraints = [models.UniqueConstraint(fields=('is_active',), condition=models.Q(is_active=True),
                                               name='one_active_score_matrix_version')]

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first()

    @property
    def in_use(self):
        return self.scores.exists()

    def copy(self, name):
        """A new, inactive version with the same rows, to edit before activating it."""
        new = ScoreMatrixVersion.objects.create(name=name, note=_('Copy of %s') % self.name)
        ScoreMatrix.objects.bulk_create(
            ScoreMatrix(**{f.name: getattr(row, f.name) for f in ScoreMatrix._meta.concrete_fields
                           if f.name not in ('id', 'version')}, version=new)
            for row in self.rows.all())
        return new

    def activate(self):
        ScoreMatrixVersion.objects.exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.save(update_fields=['is_active'])


class ScoreMatrix(models.Model):
    version = models.ForeignKey(ScoreMatrixVersion, on_delete=models.PROTECT, related_name='rows',
                                verbose_name=_('Version'))
    score_attr = models.CharField(_("Score Attribute"), max_length=100)
    description = models.CharField(_("Description"), max_length=300)
    value_from = models.BigIntegerField(_("Value From"), blank=True, null=True)
    value_to = models.BigIntegerField(_("Value To"), blank=True, null=True)
    value_description = models.CharField(_("Score Description"), max_length=300)
    score_weight = models.IntegerField(_("Score Weight"),default=0)
    adjusted_score= models.DecimalField(_("Adjuted Score"),default=0, max_digits =10, decimal_places=3)
    scr_index= models.SmallIntegerField(_('Index'),default=1,blank=True, null=True)
    def __str__(self):
        return self.score_attr + self.description
    class Meta:
        verbose_name, verbose_name_plural = _('Score matrix row'), _('Score matrix')
        ordering = ('scr_index',)

class ScoreDetail(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete = models.CASCADE, related_name='score', verbose_name = _("Ticket"))
    matrix_version = models.ForeignKey(ScoreMatrixVersion, on_delete=models.PROTECT, related_name='scores',
                                       null=True, blank=True, verbose_name=_('Score matrix version'))
    scored_at = models.DateTimeField(_('Scored at'), null=True, blank=True)
    age = models.IntegerField(_('Age'),blank=True,null=True)
    mortgagor = models.IntegerField(_('Mortgagor'),blank=True,null=True)
    marital = models.IntegerField(_('Marital Status'), choices=LOV.MARITAL_CHOICES, default=1,blank=True,null= True,)
    numborrow = models.SmallIntegerField(_('Number of borrowers'),default =2,blank=True,null= True, )
    typeofhouse = models.SmallIntegerField(_('Type of House -  First Borrower'),default =2,blank=True,null= True, )
    length_in_service = models.SmallIntegerField(_('Length in service (months)'), blank=True,null= True,)
    employment_type = models.SmallIntegerField(_('Employment Type'), blank=True,null= True,)
    edulvl = models.IntegerField(_("Education level"), choices=LOV.EDU_CHOICES ,blank=True, null=True)
    resstat  = models.IntegerField(_("Residential Status"), choices=LOV.RESIDENTIALSTATUS_CHOICES ,blank=True, null=True)

    # Financial Data
    monthly_average = models.BigIntegerField(_('Monthly Average'), blank=True,null=True,default=1) 
    dsr = models.SmallIntegerField(_('DSR (%)'),default=0,blank=True, null=True, )
    source_income = models.SmallIntegerField(_('Sources of Income'), blank=True,null= True,default=1)

    # Application Data
    property_type = models.SmallIntegerField(_('Property Type'), blank=True,null= True,)
    collateral_type = models.SmallIntegerField(_('Collateral Type'), blank=True,null= True,)
    loan_term = models.SmallIntegerField(_('Loan Term (Months)'),blank=True,null=True,)
    loan_value_ratio = models.SmallIntegerField(_('Loan to Value Ratio'),default=1,blank=True, null=True)
    loan_amount = models.BigIntegerField(_('Loan amount (VND)'),blank=True,null=True,default=1,)
    mortgage_loan_type = models.SmallIntegerField(_('Mortgage Loans Type'),blank=True,null=True,default=1)
    loan_moa = models.SmallIntegerField(_('Overall Margin of Advance (MOA)'),default=1,blank=True, null=True)

    # Internal and credit bureau data, entered by CED
    AGE_ACCOUNT_CHOICES = ((0, _('0')), (1, _('< 1 year')), (3, _('1-<=3 years')), (4, _('>3 years')))
    CONDUCT_CHOICES = ((0, _('New Borrower')), (1, _('Group 1')), (2, _('Group 2')), (3, _('Group 3 and above')))
    INSTITUTIONS_CHOICES = ((-1, _('No Bureau Match')), (0, _('0')), (1, _('1')), (2, _('2')), (3, _('3')),
                            (4, _('4+')), (5, _('No Information/ Missing Value')))
    DEFAULTS_CHOICES = ((-1, _('No Bureau Match')), (0, _('0')), (1, _('1')), (2, _('2')), (3, _('3+')),
                        (5, _('No Information/ Missing Value')))
    age_borrower_acc = models.SmallIntegerField(_('Age of account (years)'), choices=AGE_ACCOUNT_CHOICES, default=0,
                                                blank=True, null=True)
    conduct_acc = models.SmallIntegerField(_('Conduct of account at Bank'), choices=CONDUCT_CHOICES, default=0,
                                           blank=True, null=True)
    where_report = models.SmallIntegerField(_('Where Bureau report is available'), choices=LOV.BOOL_CHOICES,
                                            default=1, blank=True, null=True)
    num_CI = models.SmallIntegerField(_('Number of Credit Institutions banked with'), choices=INSTITUTIONS_CHOICES,
                                      default=0, blank=True, null=True)
    no12_Defaults = models.SmallIntegerField(_('No of Defaults (in the Last 12 months)'), choices=DEFAULTS_CHOICES,
                                             default=0, blank=True, null=True)
    no60_Defaults = models.SmallIntegerField(_('No of Defaults (in the Last 60 months)'), choices=DEFAULTS_CHOICES,
                                             default=0, blank=True, null=True)

    def __str__(self):
        return self.ticket.title

    class Meta:
        verbose_name, verbose_name_plural = _('CRR scoring input'), _('CRR scoring inputs')

class CreditAssessment(models.Model):
    """Income, repayment capacity and CRR result of an application, recalculated from its records."""
    EMPLOYMENT_CHOICES = ((1, _('Self Employed')), (2, _('Employed')), (3, _('Others')), (4, _('No Infomation')))

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, primary_key=True, verbose_name=_('Application'))
    lengthinservice = models.SmallIntegerField(_('Length in service'), default=2, blank=True, null=True)
    employment_type = models.SmallIntegerField(_('Employment Type'), choices=EMPLOYMENT_CHOICES, blank=True,
                                               null=True)
    # Monthly income
    net_income = models.BigIntegerField(_('Net salary/ Net profit (VND)'), default=0, blank=True, null=True)
    biz_income = models.BigIntegerField(_('Income from Business(VND)'), default=0, blank=True, null=True)
    hhold_income = models.BigIntegerField(_('Income from Household (VND)'), default=0, blank=True, null=True)
    rental_income = models.BigIntegerField(_('Income from leased assets (VND)'), default=0, blank=True, null=True)
    monthly_income = models.BigIntegerField(_('Total Monthly income (VND)'), default=0, blank=True, null=True)
    crr_biz_income = models.BigIntegerField(_('Income from Biz activity (VND)'), default=0, blank=True, null=True)
    segmentation = models.CharField(_('Income Segmentation'), blank=True, null=True, max_length=100)
    tatsegmentation = models.CharField(_('Segmentation for TAT'), blank=True, null=True, max_length=100)
    # Repayment capacity
    exist_highest_installment = models.BigIntegerField(_('Existing Highest Installment(VND)'), default=0, blank=True,
                                                       null=True)
    exist_average_installment = models.BigIntegerField(_('Existing Average Installment (VND)'), default=0,
                                                       blank=True, null=True)
    expenditure = models.BigIntegerField(_('Total Monthly Expenditure'), default=0, blank=True, null=True)
    dsr_high = models.DecimalField(_('Highest DSR (%)'), default=0, blank=True, null=True, max_digits=10,
                                   decimal_places=3)
    dsr_avg = models.DecimalField(_('Average DSR (%)'), default=0, blank=True, null=True, max_digits=10,
                                  decimal_places=3)
    nst = models.BigIntegerField(_('NST(>0)'), default=0, blank=True, null=True)
    # CRR scoring result
    crr_score = models.CharField(_('CRR score'), max_length=10, blank=True, null=True)
    crr_band = models.CharField(_('CRR band'), max_length=10, blank=True, null=True)

    class Meta:
        verbose_name = _('Credit assessment')

    def __str__(self):
        return self.ticket.title


class CraLoanSaleParty(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete = models.CASCADE, verbose_name = _("Ticket"))
    cra_salepart_name = models.CharField(_('Họ và tên (ghi rõ danh xưng Ông/Bà)'), max_length=100, blank=True, null=True,) 
    cra_salepart_year= models.CharField(_('Năm sinh '), max_length=100, blank=True, null=True,) 
    cra_salepart_id= models.CharField(_('Số CMND/ CCCD/Hộ chiếu'), max_length=100, blank=True, null=True,) 
    cra_salepart_idplace= models.CharField(_('Nơi cấp'), max_length=100, blank=True, null=True,) 
    cra_salepart_peraddress= models.CharField(_('Địa chỉ thường trú'), max_length=100, blank=True, null=True,) 
    def __str__(self):
        return "%s"%self.ticket.title

    class Meta:
        verbose_name, verbose_name_plural = _('Sale party'), _('Sale parties')

















class CreditSettings(models.Model):
    """
    Credit assessment parameters editable in the admin. A single row (pk=1);
    use CreditSettings.load(). The defaults are the values the code used to
    hard-code; they are demo assumptions until the credit department confirms them.
    """
    primary_expenditure = models.BigIntegerField(
        _('Monthly living cost, primary applicant (VND)'), default=5000000)
    other_applicant_expenditure = models.BigIntegerField(
        _('Monthly living cost, each other applicant (VND)'), default=4420000)
    salary_segment_min_income = models.BigIntegerField(
        _('Minimum salary income for the SAL segment (VND)'), default=15000000)
    salary_segment_min_share = models.DecimalField(
        _('Minimum salary share of total income for SAL'), max_digits=4, decimal_places=2, default=Decimal('0.50'))
    band_size = models.PositiveIntegerField(_('Score points per CRR band'), default=100)
    max_band = models.PositiveSmallIntegerField(_('Highest CRR band'), default=10)

    class Meta:
        verbose_name = _('Credit settings')
        verbose_name_plural = _('Credit settings')

    def __str__(self):
        return str(_('Credit settings'))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings_row, _created = cls.objects.get_or_create(pk=1)
        return settings_row


class CreditPolicy(models.Model):
    """
    Credit policy limits of a product (or the default, without a product). An
    application outside a limit is flagged with the deviation code to declare.
    """
    product_code = models.IntegerField(_('Product code'), null=True, blank=True, unique=True,
                                       help_text=_('Empty: the default for products without their own policy.'))
    max_dsr = models.DecimalField(_('Maximum DSR (%)'), max_digits=6, decimal_places=2, null=True, blank=True)
    max_ltv = models.DecimalField(_('Maximum loan to value (%)'), max_digits=6, decimal_places=2, null=True,
                                  blank=True)
    max_tenor = models.PositiveIntegerField(_('Maximum tenor (months)'), null=True, blank=True)
    max_age_at_maturity = models.PositiveIntegerField(_('Maximum age at maturity (years)'), null=True, blank=True)
    min_monthly_income = models.BigIntegerField(_('Minimum monthly income (VND)'), null=True, blank=True)
    min_net_surplus = models.BigIntegerField(_('Minimum net surplus after payments (VND)'), null=True, blank=True)
    max_loan_amount = models.BigIntegerField(_('Maximum loan amount (VND)'), null=True, blank=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Credit policy'), _('Credit policies')
        ordering = ('product_code',)

    def __str__(self):
        return str(_('Policy for product %s') % self.product_code if self.product_code else _('Default policy'))

    @classmethod
    def for_product(cls, product_code):
        return cls.objects.filter(product_code=product_code).first() or cls.objects.filter(product_code=None).first()


class ContractTemplate(models.Model):
    """
    A Word template for a contract document type. The business uploads it; the
    placeholders ({{ borrower.name }}, ...) are filled from the application.
    Without an active template for a type, the default in lwf/contract_templates/ is used.
    """
    contract_type = models.IntegerField(_('Contract type'), choices=CraDocInfo.CRA_DOC_TYPES)
    name = models.CharField(_('Name'), max_length=200)
    file = models.FileField(_('Word template (.docx)'), upload_to='lwf/contract_templates/')
    is_active = models.BooleanField(_('Active'), default=True)
    updated = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Contract template'), _('Contract templates')
        ordering = ('contract_type', '-updated')
        constraints = [models.UniqueConstraint(fields=('contract_type',), condition=models.Q(is_active=True),
                                               name='one_active_template_per_contract_type')]

    def __str__(self):
        return self.name


class Notification(models.Model):
    """Something a user should know about an application: shown in the app until read."""
    ASSIGNED, SENT_BACK, CLOSED, REASSIGNED, DUE_SOON, OVERDUE = 'assigned', 'sent_back', 'closed', 'reassigned', \
        'due_soon', 'overdue'
    DISBURSED = 'disbursed'
    KINDS = ((ASSIGNED, _('Handed to you')), (SENT_BACK, _('Sent back to you')), (CLOSED, _('Rejected or closed')),
             (REASSIGNED, _('Re-assigned to you')), (DUE_SOON, _('Due soon')), (OVERDUE, _('Overdue')),
             (DISBURSED, _('Disbursed by core banking')))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications',
                             verbose_name=_('User'))
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='notifications',
                               verbose_name=_('Application'))
    kind = models.CharField(_('Kind'), max_length=20, choices=KINDS)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+', verbose_name=_('By'))
    status = models.IntegerField(_('Status'), choices=Ticket.STATUS_CHOICES, null=True, blank=True)
    # The due date a reminder was about, so the same reminder is not sent twice.
    due_date = models.DateTimeField(_('Due'), null=True, blank=True)
    created = models.DateTimeField(_('Time'), auto_now_add=True)
    read_at = models.DateTimeField(_('Read'), null=True, blank=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Notification'), _('Notifications')
        ordering = ('-created',)
        indexes = [models.Index(fields=('user', 'read_at'))]

    def __str__(self):
        return self.message

    @property
    def message(self):
        person = (self.actor.get_full_name() or self.actor.username) if self.actor else ''
        texts = {
            self.ASSIGNED: _('%(person)s handed %(app)s to you: %(status)s.'),
            self.SENT_BACK: _('%(person)s sent %(app)s back to you: %(status)s.'),
            self.CLOSED: _('%(app)s was rejected or closed by %(person)s.'),
            self.REASSIGNED: _('%(person)s re-assigned %(app)s to you.'),
            self.DUE_SOON: _('%(app)s is due within a day.'),
            self.OVERDUE: _('%(app)s is overdue.'),
            self.DISBURSED: _('Core banking recorded the disbursement of %(app)s.'),
        }
        return texts[self.kind] % {'person': person, 'app': self.ticket.title,
                                    'status': self.get_status_display() or ''}


# ---------------------------------------------------------------- API and integrations

def _key_hash(raw):
    import hashlib
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_key(kind):
    """A random key 'lwf_<kind>_<prefix>.<secret>'; only its hash is stored, the prefix finds it."""
    import secrets
    prefix = secrets.token_hex(4)
    return prefix, 'lwf_%s_%s.%s' % (kind, prefix, secrets.token_urlsafe(32))


def _prefix_of(raw):
    try:
        return raw.split('_', 2)[2].split('.', 1)[0]
    except (AttributeError, IndexError):
        return None


class ApiClient(models.Model):
    """
    Another system that calls the API with a key (X-API-Key header). The key is
    shown once when made; only its hash is kept. Scopes say what the system may do.
    """
    APPLICATIONS_READ, PERSONAL_DATA, REFERENCE_READ = 'applications:read', 'applications:personal', 'reference:read'
    CORE_BANKING, CIC, EKYC = 'core_banking', 'cic', 'ekyc'
    SCOPES = ((APPLICATIONS_READ, _('Read applications')),
              (PERSONAL_DATA, _('Full personal data (ID numbers, addresses)')),
              (REFERENCE_READ, _('Read reference data')),
              (CORE_BANKING, _('Core banking: disbursements')),
              (CIC, _('Send credit bureau (CIC) reports')),
              (EKYC, _('Send eKYC results')))

    name = models.CharField(_('System'), max_length=100, unique=True)
    scopes = models.JSONField(_('Scopes'), default=list)
    allowed_ips = models.TextField(_('Allowed IP addresses'), blank=True,
                                   help_text=_('One per line. Empty: any address.'))
    key_prefix = models.CharField(_('Key prefix'), max_length=8, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(_('Active'), default=True)
    created = models.DateTimeField(_('Created'), auto_now_add=True)
    last_used = models.DateTimeField(_('Last used'), null=True, blank=True, editable=False)

    class Meta:
        verbose_name, verbose_name_plural = _('API client'), _('API clients')
        ordering = ('name',)

    def __str__(self):
        return self.name

    def new_key(self):
        """Give the client a new key (the old one stops working) and return it, to show once."""
        self.key_prefix, raw = _new_key('key')
        self.key_hash = _key_hash(raw)
        return raw

    @classmethod
    def from_key(cls, raw):
        import hmac
        client = cls.objects.filter(key_prefix=_prefix_of(raw) or '', is_active=True).first()
        if client and hmac.compare_digest(client.key_hash, _key_hash(raw)):
            return client
        return None

    def allows_ip(self, ip):
        allowed = [line.strip() for line in self.allowed_ips.splitlines() if line.strip()]
        return not allowed or ip in allowed

    def has_scope(self, scope):
        return scope in self.scopes


class ApiToken(models.Model):
    """A sign-in token for a person using an app (Authorization: Bearer ...); acts with that person's rights."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_tokens',
                             verbose_name=_('User'))
    device = models.CharField(_('Device'), max_length=100, blank=True)
    key_prefix = models.CharField(max_length=8, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    created = models.DateTimeField(_('Created'), auto_now_add=True)
    expires = models.DateTimeField(_('Expires'))
    last_used = models.DateTimeField(_('Last used'), null=True, blank=True)

    class Meta:
        verbose_name, verbose_name_plural = _('App sign-in token'), _('App sign-in tokens')
        ordering = ('-created',)

    def __str__(self):
        return '%s (%s)' % (self.user, self.device or '-')

    @classmethod
    def issue(cls, user, device='', hours=12):
        prefix, raw = _new_key('tok')
        token = cls.objects.create(user=user, device=device[:100], key_prefix=prefix, key_hash=_key_hash(raw),
                                   expires=timezone.now() + datetime.timedelta(hours=hours))
        return token, raw

    @classmethod
    def from_key(cls, raw):
        import hmac
        token = (cls.objects.select_related('user')
                 .filter(key_prefix=_prefix_of(raw) or '', expires__gt=timezone.now()).first())
        if token and token.user.is_active and hmac.compare_digest(token.key_hash, _key_hash(raw)):
            return token
        return None


class ApiRequestLog(models.Model):
    """Every API call: who, what, the answer and how long it took."""
    client = models.ForeignKey(ApiClient, on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name=_('API client'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name=_('User'))
    method = models.CharField(_('Method'), max_length=10)
    path = models.CharField(_('Path'), max_length=300)
    status = models.PositiveSmallIntegerField(_('Status code'))
    ip = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    duration_ms = models.PositiveIntegerField(_('Duration (ms)'))
    created = models.DateTimeField(_('Time'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name, verbose_name_plural = _('API call'), _('API calls')
        ordering = ('-created',)

    def __str__(self):
        return '%s %s %s' % (self.method, self.path, self.status)


class Disbursement(models.Model):
    """A disbursement the core banking system reports; `reference` makes a repeated report harmless."""
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='disbursements',
                               verbose_name=_('Application'))
    reference = models.CharField(_('Core banking reference'), max_length=64, unique=True)
    amount = models.BigIntegerField(_('Amount (VND)'))
    disbursed_at = models.DateTimeField(_('Disbursed at'))
    account_number = models.CharField(_('Loan account number'), max_length=50)
    client = models.ForeignKey(ApiClient, on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name=_('API client'))
    created = models.DateTimeField(_('Received'), auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Disbursement'), _('Disbursements')
        ordering = ('-disbursed_at',)

    def __str__(self):
        return '%s %s' % (self.ticket, self.reference)


class CicReport(models.Model):
    """A credit bureau report of an applicant, as received; its loans become the applicant's CIC records."""
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='cic_reports',
                                  verbose_name=_('Applicant'))
    report_date = models.DateField(_('Report date'))
    source = models.CharField(_('Source'), max_length=100)
    credit_group = models.CharField(_('Credit record in last 5Y'), max_length=10, blank=True)
    data = models.JSONField(_('Report'))
    created = models.DateTimeField(_('Received'), auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = _('CIC report'), _('CIC reports')
        ordering = ('-created',)

    def __str__(self):
        return '%s %s' % (self.applicant, self.report_date)


class EkycCheck(models.Model):
    """The result of reading an applicant's chip ID card and matching the face, compared with the application."""
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='ekyc_checks',
                                  verbose_name=_('Applicant'))
    data = models.JSONField(_('Data read'))
    chip_verified = models.BooleanField(_('Chip verified'), default=False)
    face_match_score = models.DecimalField(_('Face match score'), max_digits=5, decimal_places=2, null=True,
                                           blank=True)
    passed = models.BooleanField(_('Passed'))
    mismatches = models.JSONField(_('Differences'), default=list)
    source = models.CharField(_('Source'), max_length=100)
    created = models.DateTimeField(_('Time'), auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = _('eKYC check'), _('eKYC checks')
        ordering = ('-created',)

    def __str__(self):
        return '%s %s' % (self.applicant, self.created)


class DocumentExtraction(models.Model):
    """Fields read from an uploaded document by AI; a person checks them before applying them."""
    document = models.ForeignKey(AttachDocument, on_delete=models.CASCADE, related_name='extractions',
                                 verbose_name=_('Document'))
    kind = models.CharField(_('Document kind'), max_length=30)
    data = models.JSONField(_('Fields read'), default=dict)
    model_name = models.CharField(_('AI model'), max_length=100, blank=True)
    error = models.TextField(_('Error'), blank=True)
    created = models.DateTimeField(_('Time'), auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name=_('By'))
    applied_at = models.DateTimeField(_('Applied'), null=True, blank=True)

    class Meta:
        verbose_name, verbose_name_plural = _('Document reading'), _('Document readings')
        ordering = ('-created',)

    def __str__(self):
        return '%s %s' % (self.document, self.kind)
