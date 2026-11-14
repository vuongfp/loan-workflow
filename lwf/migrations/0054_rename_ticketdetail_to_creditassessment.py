from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lwf', '0053_drop_split_fields'),
    ]

    operations = [
        migrations.RenameModel('TicketDetail', 'CreditAssessment'),
        migrations.RenameField('creditassessment', 'crr_mortgage', 'crr_score'),
        migrations.RenameField('creditassessment', 'crr_mortgage_band', 'crr_band'),
    ]
