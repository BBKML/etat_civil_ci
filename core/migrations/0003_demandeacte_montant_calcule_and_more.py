# Generated by Django 5.1.7 on 2025-05-31 13:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_personne_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeacte',
            name='montant_calcule',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='demandeacte',
            name='montant_total',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='demandeacte',
            name='paiement_requis',
            field=models.BooleanField(default=True),
        ),
    ]
