# Generated by Django 5.1.7 on 2025-06-01 11:55

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_paiement_agent_confirmateur_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='paiement',
            options={},
        ),
        migrations.RemoveIndex(
            model_name='paiement',
            name='core_paieme_statut_77e647_idx',
        ),
        migrations.RemoveIndex(
            model_name='paiement',
            name='core_paieme_date_pa_820346_idx',
        ),
        migrations.RenameField(
            model_name='paiement',
            old_name='date_paiement',
            new_name='date_creation',
        ),
        migrations.RenameField(
            model_name='paiement',
            old_name='date_confirmation',
            new_name='date_validation',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='code_erreur',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='commentaire',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='date_expiration',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='date_remboursement',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='demande',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='message_erreur',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='methode_paiement',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='montant_timbres',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='montant_total',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='numero_telephone',
        ),
        migrations.RemoveField(
            model_name='paiement',
            name='reference_externe',
        ),
        migrations.AddField(
            model_name='paiement',
            name='demande_acte',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='core.demandeacte'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='paiement',
            name='mode_paiement',
            field=models.CharField(choices=[('CINETPAY', 'CinetPay'), ('ESPECES', 'Espèces'), ('VIREMENT', 'Virement')], default='CINETPAY', max_length=20),
        ),
        migrations.AddField(
            model_name='paiement',
            name='transaction_id',
            field=models.CharField(default=1, max_length=100, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='paiement',
            name='agent_confirmateur',
            field=models.ForeignKey(blank=True, help_text='Agent qui a confirmé le paiement', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paiements_confirmes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='paiement',
            name='reference_transaction',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='paiement',
            name='statut',
            field=models.CharField(choices=[('EN_ATTENTE', 'En attente'), ('VALIDE', 'Validé'), ('ECHEC', 'Échec'), ('ANNULE', 'Annulé')], default='EN_ATTENTE', max_length=20),
        ),
    ]
