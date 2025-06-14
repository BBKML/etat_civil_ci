from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from core.models import Commune, Personne, DemandeActe, Paiement, DocumentNumerique
from django.db import transaction
from datetime import date

class Command(BaseCommand):
    help = "Test des rôles: citoyen, agent, admin"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        # Vérifier qu'une commune existe
        commune = Commune.objects.first()
        if not commune:
            self.stdout.write(self.style.ERROR("❌ Aucune commune trouvée."))
            return

        try:
            with transaction.atomic():
                # Création ou récupération du citoyen
                citoyen, created = User.objects.get_or_create(
                    username='citoyen_test',
                    defaults={
                        'password': make_password('test1234'),  # Hash le mot de passe
                        'role': 'CITOYEN',
                        'first_name': 'Jean',
                        'last_name': 'Kouassi',
                        'commune': commune,
                        'email': 'citoyen@test.com'  # Ajout de l'email
                    }
                )
                if created:
                    self.stdout.write(f"✅ Citoyen créé: {citoyen.username}")

                # Création ou récupération de l'agent
                agent, created = User.objects.get_or_create(
                    username='agent_test',
                    defaults={
                        'password': make_password('test1234'),
                        'role': 'AGENT_COMMUNE',
                        'commune': commune,
                        'first_name': 'Agent',
                        'last_name': 'Test',
                        'email': 'agent@test.com'
                    }
                )
                if created:
                    self.stdout.write(f"✅ Agent créé: {agent.username}")

                # Création ou récupération de l'admin
                admin, created = User.objects.get_or_create(
                    username='admin_test',
                    defaults={
                        'password': make_password('test1234'),
                        'role': 'ADMINISTRATEUR',
                        'is_superuser': True,
                        'is_staff': True,
                        'commune': commune,
                        'first_name': 'Admin',
                        'last_name': 'Test',
                        'email': 'admin@test.com'
                    }
                )
                if created:
                    self.stdout.write(f"✅ Admin créé: {admin.username}")

                # Création ou récupération de la personne
                personne, created = Personne.objects.get_or_create(
                    user=citoyen,
                    defaults={
                        'nom': 'Kouassi',
                        'prenoms': 'Jean Junior',
                        'date_naissance': date(2000, 1, 1),  # Utiliser date() au lieu de string
                        'lieu_naissance': 'Yamoussoukro',
                        'sexe': 'M',
                        'commune_naissance': commune,
                        'commune_residence': commune
                    }
                )
                if created:
                    self.stdout.write(f"✅ Personne créée: {personne.nom} {personne.prenoms}")

                # Création de la demande avec tous les champs obligatoires
                demande, created = DemandeActe.objects.get_or_create(
                    demandeur=citoyen,
                    personne_concernee=personne,
                    defaults={
                        'type_acte': 'CERTIFICAT_NAISSANCE',  # Champ obligatoire manquant
                        'commune_traitement': commune,
                        'statut': 'EN_ATTENTE',
                        'nombre_copies': 1,
                        'motif_demande': 'PERSONNEL',
                        'lien_avec_personne': 'LUI_MEME',
                        'mode_retrait': 'SUR_PLACE'
                    }
                )
                if created:
                    self.stdout.write(f"✅ Demande créée: {demande.numero_demande}")
                else:
                    self.stdout.write(f"✅ Demande existante: {demande.numero_demande}")

                # Création du paiement
                paiement, created = Paiement.objects.get_or_create(
                    demande=demande,
                    defaults={
                        'montant': 2000,
                        'montant_timbres': 500,
                        'montant_total': 2500,
                        'methode_paiement': 'MOBILE_MONEY',
                        'numero_telephone': '+22501020304',
                        'statut': 'EN_ATTENTE',
                        'reference_transaction': 'TEST12345'
                    }
                )
                if created:
                    self.stdout.write(f"✅ Paiement créé: {paiement.reference_transaction}")

                # Création du document
                doc, created = DocumentNumerique.objects.get_or_create(
                    demande=demande,
                    defaults={
                        'type_document': 'ACTE_OFFICIEL',
                        'fichier': 'documents_etat_civil/test.pdf'
                    }
                )
                if created:
                    self.stdout.write(f"✅ Document créé: {doc.type_document}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création: {str(e)}"))
            return

        # ========== TESTS ==========
        self.stdout.write(self.style.SUCCESS("\n🔍 === TESTS DES RÔLES ==="))
        
        self.stdout.write(self.style.WARNING("\n--- Test du CITOYEN ---"))
        citoyen_demandes = DemandeActe.objects.filter(demandeur=citoyen).count()
        citoyen_paiements = Paiement.objects.filter(demande__demandeur=citoyen).count()
        citoyen_docs = DocumentNumerique.objects.filter(demande__demandeur=citoyen).count()
        
        self.stdout.write(f"📄 Demandes visibles : {citoyen_demandes}")
        self.stdout.write(f"💰 Paiements visibles : {citoyen_paiements}")
        self.stdout.write(f"📁 Documents visibles : {citoyen_docs}")

        self.stdout.write(self.style.WARNING("\n--- Test de l'AGENT ---"))
        agent_personnes = Personne.objects.filter(commune_residence=agent.commune).count()
        agent_demandes = DemandeActe.objects.filter(commune_traitement=agent.commune).count()
        agent_paiements = Paiement.objects.filter(demande__commune_traitement=agent.commune).count()
        
        self.stdout.write(f"👥 Personnes visibles : {agent_personnes}")
        self.stdout.write(f"📄 Demandes visibles : {agent_demandes}")
        self.stdout.write(f"💰 Paiements visibles : {agent_paiements}")

        self.stdout.write(self.style.WARNING("\n--- Test de l'ADMIN ---"))
        admin_demandes = DemandeActe.objects.all().count()
        admin_paiements = Paiement.objects.all().count()
        admin_docs = DocumentNumerique.objects.all().count()
        
        self.stdout.write(f"📄 Toutes les demandes : {admin_demandes}")
        self.stdout.write(f"💰 Tous les paiements : {admin_paiements}")
        self.stdout.write(f"📁 Tous les documents : {admin_docs}")

        # Test des permissions spécifiques
        self.stdout.write(self.style.SUCCESS("\n🔐 === TESTS DES PERMISSIONS ==="))
        
        # Test: Le citoyen peut-il voir les demandes des autres ?
        autres_demandes = DemandeActe.objects.exclude(demandeur=citoyen).count()
        self.stdout.write(f"👁️  Autres demandes (citoyen ne devrait pas voir): {autres_demandes}")
        
        # Test: L'agent peut-il traiter les demandes de sa commune ?
        demandes_traitables = DemandeActe.objects.filter(
            commune_traitement=agent.commune,
            statut__in=['EN_ATTENTE', 'PAIEMENT_CONFIRME']
        ).count()
        self.stdout.write(f"⚙️  Demandes traitables par l'agent: {demandes_traitables}")
        
        # Test du workflow de la demande
        self.stdout.write(self.style.SUCCESS(f"\n📊 === STATUT DE LA DEMANDE ==="))
        self.stdout.write(f"🏷️  Statut actuel: {demande.get_statut_display()}")
        self.stdout.write(f"🆔 Numéro de demande: {demande.numero_demande}")
        self.stdout.write(f"🎯 Numéro de suivi: {demande.numero_suivi}")
        self.stdout.write(f"📅 Date de demande: {demande.date_demande}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Tests terminés avec succès!"))