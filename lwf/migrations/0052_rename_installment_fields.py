from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lwf', '0051_credit_decision_and_contracts'),
    ]

    operations = [
        migrations.RenameField('loandetail', 'highest_Installment', 'highest_installment'),
        migrations.RenameField('loandetail', 'lowest_Installment', 'lowest_installment'),
        migrations.RenameField('loandetail', 'average_Installment', 'average_installment'),
    ]
