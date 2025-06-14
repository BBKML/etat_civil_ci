from django.contrib.auth import get_user_model
from core.models import Commune, Personne, DemandeActe, Paiement, DocumentNumerique

def run():
    User = get_user_model()

    # ========== PRÉPARATION ==========
    commune = Commune.objects.first()
    if not commune:
        print("❌ Aucune commune trouvée.")
        return

    citoyen, _ = User.objects.get_or_create(
        username='citoyen_test',
        defaults={
            'password': 'test1234',
            'role': 'CITOYEN',
            'first_name': 'Jean',
            'last_name': 'Kouassi',
            'commune': commune
        }
    )

    agent, _ = User.objects.get_or_create(
        username='agent_test',
        defaults={
            'password': 'test1234',
            'role': 'AGENT_COMMUNE',
            'commune': commune
        }
    )

    admin, _ = User.objects.get_or_create(
        username='admin_test',
        defaults={
            'password': 'test1234',
            'role': 'ADMINISTRATEUR',
            'is_superuser': True,
            'is_staff': True,
            'commune': commune
        }
    )

    personne, _ = Personne.objects.get_or_create(
        user=citoyen,
        nom='Kouassi',
        prenoms='Jean Junior',
        date_naissance='2000-01-01',
        lieu_naissance='Yamoussoukro',
        sexe='M',
        commune_naissance=commune,
        commune_residence=commune
    )

    demande, _ = DemandeActe.objects.get_or_create(
        demandeur=citoyen,
        personne_concernee=personne,
        commune_traitement=commune,
        statut='EN_ATTENTE'
    )

    paiement, _ = Paiement.objects.get_or_create(
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

    doc, _ = DocumentNumerique.objects.get_or_create(
        demande=demande,
        type_document='ACTE_OFFICIEL',
        fichier='documents_etat_civil/test.pdf'
    )

    # ========== TESTS ==========
    print("\n--- Test du CITOYEN ---")
    print("Demandes visibles :", DemandeActe.objects.filter(demandeur=citoyen).exists())
    print("Paiements visibles :", Paiement.objects.filter(demande__demandeur=citoyen).exists())
    print("Documents visibles :", DocumentNumerique.objects.filter(demande__demandeur=citoyen).exists())

    print("\n--- Test de l’AGENT ---")
    print("Personnes visibles :", Personne.objects.filter(commune_residence=agent.commune).exists())
    print("Demandes visibles :", DemandeActe.objects.filter(commune_traitement=agent.commune).exists())
    print("Paiements visibles :", Paiement.objects.filter(demande__commune_traitement=agent.commune).exists())

    print("\n--- Test de l’ADMIN ---")
    print("Toutes les demandes :", DemandeActe.objects.all().count())
    print("Tous les paiements :", Paiement.objects.all().count())
    print("Tous les documents :", DocumentNumerique.objects.all().count())
