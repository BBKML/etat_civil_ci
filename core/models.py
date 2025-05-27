from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
import uuid
from datetime import date

# Modèle utilisateur personnalisé


# Modèle pour les régions
class Region(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    code_region = models.CharField(max_length=15, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.nom


# Modèle pour les départements
class Departement(models.Model):
    nom = models.CharField(max_length=100)
    code_departement = models.CharField(max_length=10, unique=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='departements')
    
    def __str__(self):
        return f"{self.nom} ({self.region.nom})"


# Modèle pour les sous-préfectures
class SousPrefecture(models.Model):
    nom = models.CharField(max_length=100)
    code_sous_prefecture = models.CharField(max_length=10, unique=True)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE, related_name='sous_prefectures')
    adresse = models.TextField()
    telephone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    
    def __str__(self):
        return f"{self.nom} - {self.departement.nom}"


# Modèle pour les communes
class Commune(models.Model):
    nom = models.CharField(max_length=100)
    code_commune = models.CharField(max_length=10, unique=True)
    sous_prefecture = models.ForeignKey(SousPrefecture, on_delete=models.CASCADE, related_name='communes')
    adresse = models.TextField()
    telephone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    site_web = models.URLField(blank=True)
    
    def __str__(self):
        return f"{self.nom} - {self.sous_prefecture.nom}"

class User(AbstractUser):
    ROLE_CHOICES = [
        ('CITOYEN', 'Citoyen'),
        ('AGENT_COMMUNE', 'Agent de Commune'),
        ('AGENT_SOUS_PREFECTURE', 'Agent de Sous-Préfecture'),
        ('ADMINISTRATEUR', 'Administrateur'),
        ('MAIRE', 'Maire'),
        ('SOUS_PREFET', 'Sous-Préfet'),
    ]
    telephone = models.CharField(max_length=15, blank=True)
    adresse = models.TextField(blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='CITOYEN')
    numero_cni = models.CharField(max_length=25, unique=True, blank=True, null=True)
    commune = models.ForeignKey(
        'Commune',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Commune associée'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    photo = models.ImageField(upload_to='photos/', null=True, blank=True)


    def clean(self):
        super().clean()
        role = getattr(self, 'role', None)
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE'] and not self.commune:
            raise ValidationError(
                'Une commune doit être spécifiée pour ce rôle'
            )
        
    def save(self, *args, **kwargs):
        # Vérifier si on modifie des champs protégés
        if self.pk and not (self.is_superuser or self.role == 'ADMINISTRATEUR'):
            original = User.objects.get(pk=self.pk)
            protected_fields = ['role', 'commune', 'is_verified']
            for field in protected_fields:
                if getattr(original, field) != getattr(self, field):
                    raise PermissionDenied(f"Vous n'avez pas le droit de modifier le champ {field}")
        super().save(*args, **kwargs)   
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"
# Modèle pour les personnes
class Personne(models.Model):
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    SITUATION_MATRIMONIALE_CHOICES = [
        ('CELIBATAIRE', 'Célibataire'),
        ('MARIE', 'Marié(e)'),
        ('DIVORCE', 'Divorcé(e)'),
        ('VEUF', 'Veuf/Veuve'),
    ]
    
    # Champs existants (corrects)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    numero_unique = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=200)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=200)
    commune_naissance = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True, related_name='personnes_nees')
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    profession = models.CharField(max_length=100, blank=True)
    adresse_actuelle = models.TextField(blank=True)
    situation_matrimoniale = models.CharField(max_length=15, choices=SITUATION_MATRIMONIALE_CHOICES, default='CELIBATAIRE')
    
    # AMÉLIORATION 1: Noms complets des parents avec prénoms
    nom_pere = models.CharField(max_length=100, blank=True, verbose_name="Nom du père")
    prenoms_pere = models.CharField(max_length=150, blank=True, verbose_name="Prénoms du père")
    nom_mere = models.CharField(max_length=100, blank=True, verbose_name="Nom de la mère")
    prenoms_mere = models.CharField(max_length=150, blank=True, verbose_name="Prénoms de la mère")
    
    # AMÉLIORATION 2: Informations complémentaires importantes
    nationalite = models.CharField(max_length=50, default="Ivoirienne")
    commune_residence = models.ForeignKey(
        Commune, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='residents',
        verbose_name="Commune de résidence actuelle"
    )
    
    # AMÉLIORATION 3: Contacts
    telephone = models.CharField(
        max_length=15, 
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{8,15}$', 'Numéro invalide')]
    )
    email = models.EmailField(blank=True)
    
    # AMÉLIORATION 4: Statut vital
    est_vivant = models.BooleanField(default=True)
    
    # Champs existants (corrects)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['email','telephone']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telephone']),

          
        ]
        
    def clean(self):
        # Validation âge
        if self.date_naissance and self.date_naissance > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur")
        
        # Validation cohérence situation matrimoniale
        if self.situation_matrimoniale == 'MARIE':
            # Vérifier qu'il existe un mariage non dissous
            if not hasattr(self, 'mariages_epoux') and not hasattr(self, 'mariages_epouse'):
                pass  # On peut valider plus tard avec les mariage
  
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )
    

    def __str__(self):
        return f"{self.nom} {self.prenoms}"


# Modèle pour les actes de naissance
class ActeNaissance(models.Model):
    numero_acte = models.CharField(max_length=50, unique=True)
    personne = models.OneToOneField(Personne, on_delete=models.CASCADE, related_name='acte_naissance')
    commune_enregistrement = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='actes_naissance')
    date_enregistrement = models.DateField()
    numero_registre = models.CharField(max_length=20)
    page_registre = models.CharField(max_length=10)
    declarant_nom = models.CharField(max_length=100)
    declarant_qualite = models.CharField(max_length=50)  # père, mère, témoin, etc.
    temoin1_nom = models.CharField(max_length=100, blank=True)
    temoin2_nom = models.CharField(max_length=100, blank=True)
    observations = models.TextField(blank=True)
    agent_enregistreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Acte N° {self.numero_acte} - {self.personne.nom} {self.personne.prenoms}"


# Modèle pour les mariages
class Mariage(models.Model):
    REGIME_MATRIMONIAL_CHOICES = [
        ('COMMUNAUTE', 'Communauté de biens'),
        ('SEPARATION', 'Séparation de biens'),
        ('PARTICIPATION', 'Participation aux acquêts'),
    ]
    
    numero_acte = models.CharField(max_length=50, unique=True)
    epoux = models.ForeignKey(Personne, on_delete=models.CASCADE, related_name='mariages_epoux')
    epouse = models.ForeignKey(Personne, on_delete=models.CASCADE, related_name='mariages_epouse')
    date_mariage = models.DateField()
    commune_mariage = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='mariages')
    regime_matrimonial = models.CharField(max_length=15, choices=REGIME_MATRIMONIAL_CHOICES, default='COMMUNAUTE')
    temoin_epoux_1 = models.CharField(max_length=100)
    temoin_epoux_2 = models.CharField(max_length=100)
    temoin_epouse_1 = models.CharField(max_length=100)
    temoin_epouse_2 = models.CharField(max_length=100)
    officier_etat_civil = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    numero_registre = models.CharField(max_length=20)
    page_registre = models.CharField(max_length=10)
    observations = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Mariage N° {self.numero_acte} - {self.epoux.nom} & {self.epouse.nom}"


# Modèle pour les décès
class ActeDeces(models.Model):
    numero_acte = models.CharField(max_length=50, unique=True)
    personne = models.OneToOneField(Personne, on_delete=models.CASCADE, related_name='acte_deces')
    date_deces = models.DateField()
    heure_deces = models.TimeField(blank=True, null=True)
    lieu_deces = models.CharField(max_length=200)
    commune_deces = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='actes_deces')
    cause_deces = models.TextField(blank=True)
    declarant_nom = models.CharField(max_length=100)
    declarant_qualite = models.CharField(max_length=50)
    medecin_nom = models.CharField(max_length=100, blank=True)
    numero_certificat_medical = models.CharField(max_length=50, blank=True)
    numero_registre = models.CharField(max_length=20)
    page_registre = models.CharField(max_length=10)
    agent_enregistreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Décès N° {self.numero_acte} - {self.personne.nom} {self.personne.prenoms}"


# Modèle pour les demandes d'actes
class DemandeActe(models.Model):
    TYPE_ACTE_CHOICES = [
        ('NAISSANCE', 'Acte de Naissance'),
        ('MARIAGE', 'Acte de Mariage'),
        ('DECES', 'Acte de Décès'),
        ('CERTIFICAT_NAISSANCE', 'Certificat de Naissance'),
        ('CERTIFICAT_MARIAGE', 'Certificat de Mariage'),
        ('CERTIFICAT_DECES', 'Certificat de Décès'),
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_ATTENTE_PAIEMENT', 'En attente de paiement'),  # NOUVEAU
        ('PAIEMENT_CONFIRME', 'Paiement confirmé'),         # NOUVEAU
        ('EN_COURS', 'En cours de traitement'),
        ('APPROUVE', 'Approuvé'),
        ('REJETE', 'Rejeté'),
        ('DELIVRE', 'Délivré'),
        ('ANNULE', 'Annulé'),                               # NOUVEAU
    ]
    
    MOTIF_DEMANDE_CHOICES = [
        ('PERSONNEL', 'Usage personnel'),
        ('ADMINISTRATIVE', 'Démarche administrative'),
        ('JURIDIQUE', 'Procédure juridique'),
        ('SCOLAIRE', 'Inscription scolaire'),
        ('EMPLOI', 'Recherche d\'emploi'),
        ('AUTRE', 'Autre'),
    ]
    
    # Champs de base
    numero_demande = models.CharField(max_length=50, unique=True, editable=False)
    demandeur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes')
    type_acte = models.CharField(max_length=20, choices=TYPE_ACTE_CHOICES)
    personne_concernee = models.ForeignKey(Personne, on_delete=models.CASCADE, related_name='demandes_actes')
    statut = models.CharField(max_length=25, choices=STATUT_CHOICES, default='EN_ATTENTE')  # Augmenté max_length
    commune_traitement = models.ForeignKey(Commune, on_delete=models.CASCADE)
    nombre_copies = models.PositiveIntegerField(default=1)
    
    # Dates importantes
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation_preliminaire = models.DateTimeField(blank=True, null=True)  # NOUVEAU
    date_traitement = models.DateTimeField(blank=True, null=True)
    date_delivrance = models.DateTimeField(blank=True, null=True)
    
    # Informations complémentaires
    motif_demande = models.CharField(
        max_length=20, 
        choices=MOTIF_DEMANDE_CHOICES,
        default='PERSONNEL'
    )
    
    lien_avec_personne = models.CharField(
        max_length=50,
        choices=[
            ('LUI_MEME', 'Lui-même/Elle-même'),
            ('PERE', 'Père'),
            ('MERE', 'Mère'),
            ('ENFANT', 'Enfant'),
            ('CONJOINT', 'Conjoint(e)'),
            ('FRERE_SOEUR', 'Frère/Sœur'),
            ('REPRESENTANT_LEGAL', 'Représentant légal'),
            ('AUTRE', 'Autre'),
        ],
        default='LUI_MEME',
        verbose_name="Lien avec la personne concernée"
    )
    
    # Justificatifs
    piece_identite_demandeur = models.FileField(
        upload_to='justificatifs/identite/',
        null=True,
        blank=True,
        verbose_name="Pièce d'identité du demandeur"
    )
    justificatif_lien = models.FileField(
        upload_to='justificatifs/lien/',
        null=True,
        blank=True,
        verbose_name="Justificatif du lien de parenté"
    )
    
    # Traitement et agents
    agent_validateur = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='demandes_validees',
        verbose_name="Agent ayant validé la demande"
    )
    agent_traitant = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='demandes_traitees'
    )
    commentaire_agent = models.TextField(blank=True)
    commentaire_rejet = models.TextField(
        blank=True,
        verbose_name="Motif de rejet"
    )
    
    # Informations financières - MODIFIÉES
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paiement_requis = models.BooleanField(default=True)  # NOUVEAU
    montant_calcule = models.BooleanField(default=False)  # NOUVEAU - indique si le montant a été calculé
    
    # Mode de retrait
    MODE_RETRAIT_CHOICES = [
        ('SUR_PLACE', 'Retrait sur place'),
        ('COURRIER', 'Envoi par courrier'),
        ('EMAIL', 'Envoi par email'),
    ]
    mode_retrait = models.CharField(
        max_length=15,
        choices=MODE_RETRAIT_CHOICES,
        default='SUR_PLACE'
    )
    adresse_livraison = models.TextField(
        blank=True,
        verbose_name="Adresse de livraison (si applicable)"
    )
    
    # Numéro de suivi
    numero_suivi = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="Numéro de suivi public"
    )
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.nombre_copies <= 0:
            raise ValidationError("Le nombre de copies doit être supérieur à 0")
        
        if self.nombre_copies > 10:
            raise ValidationError("Maximum 10 copies par demande")
        
        # Validation du lien de parenté
        if (self.lien_avec_personne != 'LUI_MEME' and 
            self.demandeur.role == 'CITOYEN' and 
            not self.justificatif_lien):
            raise ValidationError(
                "Un justificatif de lien de parenté est requis"
            )
        
        # Validation cohérence agent/commune
        if (self.agent_traitant and self.commune_traitement and
            self.agent_traitant.commune != self.commune_traitement and
            self.agent_traitant.role not in ['ADMINISTRATEUR', 'SOUS_PREFET']):
            raise ValidationError(
                "L'agent traitant doit être affecté à la commune de traitement"
            )
        
        # Validation mode de retrait
        if self.mode_retrait == 'COURRIER' and not self.adresse_livraison:
            raise ValidationError(
                "L'adresse de livraison est requise pour l'envoi par courrier"
            )
        
        # NOUVELLE VALIDATION - Logique de paiement
        if self.statut == 'EN_COURS' and self.paiement_requis:
            if not hasattr(self, 'paiement') or self.paiement.statut != 'CONFIRME':
                raise ValidationError(
                    "Une demande ne peut être traitée qu'après confirmation du paiement"
                )

    def save(self, *args, **kwargs):
        if not self.numero_demande:
            self.numero_demande = str(uuid.uuid4())
        
        if not self.numero_suivi:
            from datetime import datetime
            year = datetime.now().year
            month = datetime.now().month
            self.numero_suivi = f"DEM{year}{month:02d}{str(uuid.uuid4())[:8].upper()}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Demande {self.numero_suivi or self.numero_demande}"
    
    # NOUVELLES MÉTHODES - Gestion du workflow avec paiement
    
    def calculer_montant(self):
        """Calcule le montant total de la demande"""
        try:
            tarif = Tarif.objects.get(type_acte=self.type_acte, actif=True)
            self.montant_total = (tarif.prix_unitaire + tarif.timbre_fiscal) * self.nombre_copies
            self.montant_calcule = True
            self.save()
            return self.montant_total
        except Tarif.DoesNotExist:
            raise ValueError(f"Aucun tarif défini pour {self.type_acte}")
    
    def valider_preliminairement(self, agent):
        """Validation préliminaire avant paiement"""
        from django.utils import timezone
        
        if self.statut != 'EN_ATTENTE':
            raise ValueError("Seules les demandes en attente peuvent être validées")
        
        if not self.montant_calcule:
            self.calculer_montant()
        
        self.statut = 'EN_ATTENTE_PAIEMENT'
        self.agent_validateur = agent
        self.date_validation_preliminaire = timezone.now()
        self.save()
        
        return True
    
    def confirmer_paiement(self):
        """Confirme le paiement et passe au statut suivant"""
        from django.utils import timezone
        
        if self.statut != 'EN_ATTENTE_PAIEMENT':
            raise ValueError("La demande doit être en attente de paiement")
        
        if not hasattr(self, 'paiement') or self.paiement.statut != 'CONFIRME':
            raise ValueError("Le paiement n'est pas confirmé")
        
        self.statut = 'PAIEMENT_CONFIRME'
        self.save()
        
        return True
    
    def commencer_traitement(self, agent):
        """Démarre le traitement après paiement confirmé"""
        from django.utils import timezone
        
        if self.statut != 'PAIEMENT_CONFIRME':
            raise ValueError("Le paiement doit être confirmé avant le traitement")
        
        self.statut = 'EN_COURS'
        self.agent_traitant = agent
        self.date_traitement = timezone.now()
        self.save()
        
        return True
    
    def approuver(self, agent, commentaire=""):
        """Approuve la demande"""
        from django.utils import timezone
        
        if self.statut != 'EN_COURS':
            raise ValueError("Seules les demandes en cours peuvent être approuvées")
        
        self.statut = 'APPROUVE'
        self.agent_traitant = agent
        self.commentaire_agent = commentaire
        self.save()
        
        return True
    
    def rejeter(self, agent, motif):
        """Rejette la demande avec remboursement"""
        from django.utils import timezone
        
        if self.statut not in ['EN_COURS', 'PAIEMENT_CONFIRME']:
            raise ValueError("Cette demande ne peut pas être rejetée")
        
        self.statut = 'REJETE'
        self.agent_traitant = agent
        self.commentaire_rejet = motif
        self.save()
        
        # Déclencher le remboursement si nécessaire
        if hasattr(self, 'paiement') and self.paiement.statut == 'CONFIRME':
            self.paiement.statut = 'REMBOURSE'
            self.paiement.save()
        
        return True
    
    def delivrer(self, agent):
        """Marque la demande comme délivrée"""
        from django.utils import timezone
        
        if self.statut != 'APPROUVE':
            raise ValueError("Seules les demandes approuvées peuvent être délivrées")
        
        self.statut = 'DELIVRE'
        self.agent_traitant = agent
        self.date_delivrance = timezone.now()
        self.save()
        
        return True
    
    @property
    def peut_etre_payee(self):
        """Vérifie si la demande peut être payée"""
        return self.statut == 'EN_ATTENTE_PAIEMENT' and self.montant_calcule
    
    @property
    def peut_etre_traitee(self):
        """Vérifie si la demande peut être traitée"""
        if not self.paiement_requis:
            return self.statut in ['EN_ATTENTE', 'PAIEMENT_CONFIRME']
        
        return (self.statut == 'PAIEMENT_CONFIRME' and 
                hasattr(self, 'paiement') and 
                self.paiement.statut == 'CONFIRME')
    
    @property
    def delai_traitement(self):
        """Calcule le délai de traitement en jours"""
        if self.date_traitement and self.date_demande:
            return (self.date_traitement - self.date_demande).days
        return None
    
    @property
    def workflow_statut(self):
        """Retourne le statut lisible du workflow"""
        workflow_map = {
            'EN_ATTENTE': 'Demande reçue, en attente de validation',
            'EN_ATTENTE_PAIEMENT': 'Demande validée, en attente de paiement',
            'PAIEMENT_CONFIRME': 'Paiement confirmé, en attente de traitement',
            'EN_COURS': 'Demande en cours de traitement',
            'APPROUVE': 'Demande approuvée, en attente de délivrance',
            'REJETE': 'Demande rejetée',
            'DELIVRE': 'Acte délivré',
            'ANNULE': 'Demande annulée'
        }
        return workflow_map.get(self.statut, self.statut)
class Paiement(models.Model):
    METHODE_PAIEMENT_CHOICES = [
        ('CARTE_BANCAIRE', 'Carte bancaire'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('ORANGE_MONEY', 'Orange Money'),
        ('MTN_MONEY', 'MTN Mobile Money'),
        ('MOOV_MONEY', 'Moov Money'),
        ('VIREMENT', 'Virement bancaire'),
        ('ESPECES', 'Espèces'),
        ('CHEQUE', 'Chèque'),
    ]
    
    STATUT_PAIEMENT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours de traitement'),     # NOUVEAU
        ('CONFIRME', 'Confirmé'),
        ('ECHEC', 'Échec'),
        ('EXPIRE', 'Expiré'),                       # NOUVEAU
        ('REMBOURSE', 'Remboursé'),
        ('ANNULE', 'Annulé'),                       # NOUVEAU
    ]
    
    # Relations
    demande = models.OneToOneField(DemandeActe, on_delete=models.CASCADE, related_name='paiement')
    
    # Informations financières
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    montant_timbres = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # NOUVEAU
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)              # NOUVEAU
    
    # Méthode et statut
    methode_paiement = models.CharField(max_length=20, choices=METHODE_PAIEMENT_CHOICES)
    statut = models.CharField(max_length=15, choices=STATUT_PAIEMENT_CHOICES, default='EN_ATTENTE')
    
    # Références et identifiants
    reference_transaction = models.CharField(max_length=100, unique=True)
    reference_externe = models.CharField(max_length=100, blank=True)  # NOUVEAU - Ref du provider
    numero_telephone = models.CharField(max_length=15, blank=True)    # NOUVEAU - Pour Mobile Money
    
    # Dates importantes
    date_paiement = models.DateTimeField(auto_now_add=True)
    date_confirmation = models.DateTimeField(blank=True, null=True)
    date_expiration = models.DateTimeField(blank=True, null=True)     # NOUVEAU
    date_remboursement = models.DateTimeField(blank=True, null=True)  # NOUVEAU
    
    # Informations complémentaires
    commentaire = models.TextField(blank=True)
    code_erreur = models.CharField(max_length=50, blank=True)         # NOUVEAU
    message_erreur = models.TextField(blank=True)                     # NOUVEAU
    
    # Agent qui a traité
    agent_confirmateur = models.ForeignKey(                           # NOUVEAU
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paiements_confirmes'
    )
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validation Mobile Money
        if self.methode_paiement in ['MOBILE_MONEY', 'ORANGE_MONEY', 'MTN_MONEY', 'MOOV_MONEY']:
            if not self.numero_telephone:
                raise ValidationError("Le numéro de téléphone est requis pour Mobile Money")
        
        # Validation montant
        if self.montant <= 0:
            raise ValidationError("Le montant doit être positif")
        
        # Calculer montant total si pas défini
        if not self.montant_total:
            self.montant_total = self.montant + self.montant_timbres
    
    def save(self, *args, **kwargs):
        # Générer référence si nécessaire
        if not self.reference_transaction:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            self.reference_transaction = f"PAY{timestamp}{str(uuid.uuid4())[:8].upper()}"
        
        # Calculer montant total
        if not self.montant_total:
            self.montant_total = self.montant + self.montant_timbres
        
        super().save(*args, **kwargs)
        
        # Mettre à jour le statut de la demande automatiquement
        self.mettre_a_jour_demande()
    
    def mettre_a_jour_demande(self):
        """Met à jour le statut de la demande selon le paiement"""
        if self.statut == 'CONFIRME' and self.demande.statut == 'EN_ATTENTE_PAIEMENT':
            self.demande.confirmer_paiement()
        elif self.statut in ['ECHEC', 'EXPIRE', 'ANNULE'] and self.demande.statut == 'EN_ATTENTE_PAIEMENT':
            # Remettre en attente si le paiement échoue
            self.demande.statut = 'EN_ATTENTE'
            self.demande.save()
    
    def confirmer(self, agent=None):
        """Confirme le paiement"""
        from django.utils import timezone
        
        if self.statut != 'EN_ATTENTE':
            raise ValueError("Seuls les paiements en attente peuvent être confirmés")
        
        self.statut = 'CONFIRME'
        self.date_confirmation = timezone.now()
        self.agent_confirmateur = agent
        self.save()
        
        return True
    
    def echec(self, code_erreur="", message_erreur=""):
        """Marque le paiement comme échoué"""
        self.statut = 'ECHEC'
        self.code_erreur = code_erreur
        self.message_erreur = message_erreur
        self.save()
        
        return True
    
    def rembourser(self, agent=None, motif=""):
        """Procède au remboursement"""
        from django.utils import timezone
        
        if self.statut != 'CONFIRME':
            raise ValueError("Seuls les paiements confirmés peuvent être remboursés")
        
        self.statut = 'REMBOURSE'
        self.date_remboursement = timezone.now()
        self.commentaire = motif
        self.agent_confirmateur = agent
        self.save()
        
        return True
    
    @property
    def peut_etre_confirme(self):
        """Vérifie si le paiement peut être confirmé"""
        return self.statut in ['EN_ATTENTE', 'EN_COURS']
    
    @property
    def peut_etre_rembourse(self):
        """Vérifie si le paiement peut être remboursé"""
        return self.statut == 'CONFIRME'
    
    @property
    def est_expire(self):
        """Vérifie si le paiement a expiré"""
        if not self.date_expiration:
            return False
        
        from django.utils import timezone
        return timezone.now() > self.date_expiration and self.statut == 'EN_ATTENTE'
    
    def __str__(self):
        return f"Paiement {self.reference_transaction} - {self.montant_total} FCFA ({self.statut})"
# Modèle pour les tarifs
class Tarif(models.Model):
    TYPE_ACTE_CHOICES = [
        ('NAISSANCE', 'Acte de Naissance'),
        ('MARIAGE', 'Acte de Mariage'),
        ('DECES', 'Acte de Décès'),
        ('CERTIFICAT_NAISSANCE', 'Certificat de Naissance'),
        ('CERTIFICAT_MARIAGE', 'Certificat de Mariage'),
        ('CERTIFICAT_DECES', 'Certificat de Décès'),
    ]
    
    type_acte = models.CharField(max_length=20, choices=TYPE_ACTE_CHOICES, unique=True)
    prix_unitaire = models.DecimalField(max_digits=8, decimal_places=2)
    timbre_fiscal = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    date_application = models.DateField(default=timezone.now)
    actif = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.type_acte} - {self.prix_unitaire} FCFA"


# Modèle pour les statistiques
class Statistique(models.Model):
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='statistiques')
    annee = models.PositiveIntegerField()
    mois = models.PositiveIntegerField()
    naissances_total = models.PositiveIntegerField(default=0)
    naissances_masculines = models.PositiveIntegerField(default=0)
    naissances_feminines = models.PositiveIntegerField(default=0)
    mariages_total = models.PositiveIntegerField(default=0)
    deces_total = models.PositiveIntegerField(default=0)
    deces_masculins = models.PositiveIntegerField(default=0)
    deces_feminins = models.PositiveIntegerField(default=0)
    demandes_total = models.PositiveIntegerField(default=0)
    demandes_traitees = models.PositiveIntegerField(default=0)
    revenus_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['commune', 'annee', 'mois']
    
    def __str__(self):
        return f"Stats {self.commune.nom} - {self.mois}/{self.annee}"


# Modèle pour les logs d'audit
class LogAudit(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10)
    table_concernee = models.CharField(max_length=50)
    objet_id = models.PositiveIntegerField()
    description = models.TextField()
    adresse_ip = models.GenericIPAddressField()
    date_action = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.table_concernee}"


# Modèle pour les documents numériques
class DocumentNumerique(models.Model):
    demande = models.ForeignKey(DemandeActe, on_delete=models.CASCADE, related_name='documents')
    type_document = models.CharField(max_length=15)
    nom_fichier = models.CharField(max_length=255)
    fichier = models.FileField(upload_to='documents_etat_civil/')
    signature_numerique = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.signature_numerique:
            raise ValidationError("Le fichier doit être signé numériquement.")

    def __str__(self):
        return f"{self.nom_fichier} ({self.type_document})"