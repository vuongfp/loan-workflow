from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

# Score matrix rows name the ScoreDetail field they score.
SCORE_ATTRS = {'marial': 'marital', 'sourceIncome': 'source_income', 'collaterall_type': 'collateral_type'}


def rename_score_attrs(apps, schema_editor, mapping=SCORE_ATTRS):
    ScoreMatrix = apps.get_model('lwf', 'ScoreMatrix')
    for old, new in mapping.items():
        ScoreMatrix.objects.filter(score_attr=old).update(score_attr=new)


def restore_score_attrs(apps, schema_editor):
    rename_score_attrs(apps, schema_editor, {new: old for old, new in SCORE_ATTRS.items()})


class Migration(migrations.Migration):
    """Fix misspelled and camelCase field names. Renames only: the data is kept."""

    dependencies = [
        ('lwf', '0049_remove_helpdesk_leftovers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField('panelproject', 'dev_regitered', 'dev_registered'),
        migrations.RenameField('panelproject', 'expDate', 'exp_date'),
        migrations.RenameField('panelcar', 'dealer_regitered', 'dealer_registered'),
        migrations.RenameField('panelcar', 'expDate', 'exp_date'),
        migrations.RenameField('applicant', 'marial', 'marital'),
        migrations.RenameField('applicant', 'highestInstallment', 'highest_installment'),
        migrations.RenameField('applicant', 'averageInstallment', 'average_installment'),
        migrations.RenameField('loandetail', 'ced_porfolio', 'ced_portfolio'),
        migrations.RenameField('loandetail', 'ced_cedrecommedation', 'ced_recommendation'),
        migrations.RenameField('loandetail', 'ced_appr1recommedation', 'ced_approver1_comment'),
        migrations.RenameField('loandetail', 'ced_appr2recommedation', 'ced_approver2_comment'),
        migrations.RenameField('collamanager', 'addressAvailable', 'address_available'),
        migrations.RenameField('collamanager', 'cra_appartment_code', 'cra_apartment_code'),
        migrations.RenameField('collamanager', 'cra_notarize_tranfer_date', 'cra_notarize_transfer_date'),
        migrations.RenameField('cicsecureloan', 'originalAmount', 'original_amount'),
        migrations.RenameField('cicsecureloan', 'interestRate', 'interest_rate'),
        migrations.RenameField('cicsecureloan', 'loanTenor', 'loan_tenor'),
        migrations.RenameField('cicsecureloan', 'outstandingLoan', 'outstanding_loan'),
        migrations.RenameField('cicsecureloan', 'progressiveDisbursement', 'progressive_disbursement'),
        migrations.RenameField('cicsecureloan', 'highestInstallment', 'highest_installment'),
        migrations.RenameField('cicoverdraft', 'interestRate', 'interest_rate'),
        migrations.RenameField('cicoverdraft', 'outstandingLoan', 'outstanding_loan'),
        migrations.RenameField('ciccreditcard', 'avgBalance6M', 'avg_balance_6m'),
        migrations.RenameField('ciccreditcard', 'proxyMinPay', 'proxy_min_pay'),
        migrations.RenameField('ciccreditcard', 'highestInstallment', 'highest_installment'),
        migrations.RenameField('scorematrix', 'ajusted_score', 'adjusted_score'),
        migrations.RenameField('scoredetail', 'marial', 'marital'),
        migrations.RenameField('scoredetail', 'sourceIncome', 'source_income'),
        migrations.RenameField('scoredetail', 'collaterall_type', 'collateral_type'),
        migrations.RenameField('ticketdetail', 'montly_income', 'monthly_income'),
        migrations.RenameField('ticketdetail', 'existHighestInstallment', 'exist_highest_installment'),
        migrations.RenameField('ticketdetail', 'existAverageInstallment', 'exist_average_installment'),
        migrations.RenameField('ticketdetail', 'mortage_type', 'mortgage_type'),
        migrations.AlterField(
            model_name='ticket',
            name='approver1',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='approver1_tickets', to=settings.AUTH_USER_MODEL, verbose_name='Approver 1 Officer'),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='approver2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='approver2_tickets', to=settings.AUTH_USER_MODEL, verbose_name='Approver 2 Officer'),
        ),
        migrations.RunPython(rename_score_attrs, restore_score_attrs),
    ]
