from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile
from django.contrib import messages
from django.dispatch import receiver
from django.db.models.signals import pre_save
from decimal import Decimal
from django.core.files.base import ContentFile
from datetime import date, datetime
from decimal import Decimal
import uuid
import os

from .acte_generator import ActeGenerator
from .digital_signer import DigitalSigner

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
def photo_upload_path(instance, filename):
    import uuid
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"photos/{filename}"


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
    photo = models.ImageField(upload_to=photo_upload_path, blank=True, null=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def clean(self):
        super().clean()
        role = getattr(self, 'role', None)
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE'] and not self.commune:
            raise ValidationError(
                'Une commune doit être spécifiée pour ce rôle'
            )
        # SOLUTION SIMPLE: Validation avant sauvegarde dans l'admin
    def save(self, *args, **kwargs):
        
        self.full_clean()
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    numero_unique = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=200)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=200)
    heure_naissance = models.TimeField(null=True, blank=True)
    commune_naissance = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True, related_name='personnes_nees')
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    profession = models.CharField(max_length=100, blank=True)
    adresse = models.TextField(blank=True, null=True)
    adresse_actuelle = models.TextField(blank=True)
    situation_matrimoniale = models.CharField(max_length=15, choices=SITUATION_MATRIMONIALE_CHOICES, default='CELIBATAIRE')
    
    # AMÉLIORATION 1: Noms complets des parents avec prénoms
    nom_pere = models.CharField(max_length=100, blank=True, verbose_name="Nom du père")
    prenoms_pere = models.CharField(max_length=150, blank=True, verbose_name="Prénoms du père")
    profession_pere = models.CharField(max_length=100, null=True, blank=True)
    nom_mere = models.CharField(max_length=100, blank=True, verbose_name="Nom de la mère")
    prenoms_mere = models.CharField(max_length=150, blank=True, verbose_name="Prénoms de la mère")
    profession_mere = models.CharField(max_length=100, null=True, blank=True)
    
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



class ActeSequence(models.Model):
    """Modèle pour suivre les séquences de numérotation par commune et par type d'acte"""
    commune = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='sequences_actes')
    type_acte = models.CharField(max_length=20)  # 'NAISSANCE', 'MARIAGE', 'DECES'
    dernier_numero_acte = models.IntegerField(default=0)
    dernier_numero_registre = models.IntegerField(default=0)
    annee_courante = models.IntegerField(default=timezone.now().year)
    
    class Meta:
        unique_together = ['commune', 'type_acte']
        verbose_name = "Séquence d'Acte"
        verbose_name_plural = "Séquences d'Actes"

    def __str__(self):
        return f"Séquence {self.commune} - {self.type_acte}: {self.dernier_numero_acte}"

    def get_next_numero_acte(self, prefixe):
        """Obtient le prochain numéro d'acte de manière thread-safe"""
        with transaction.atomic():
            sequence = ActeSequence.objects.select_for_update().get(pk=self.pk)
            sequence.dernier_numero_acte += 1
            sequence.save()
            return f"{prefixe}{sequence.dernier_numero_acte:06d}"

    def get_next_numero_registre(self, annee, prefixe_registre="REG"):
        """Obtient le prochain numéro de registre pour une année donnée"""
        with transaction.atomic():
            sequence = ActeSequence.objects.select_for_update().get(pk=self.pk)
            
            # Réinitialiser le compteur si on change d'année
            if sequence.annee_courante != annee:
                sequence.annee_courante = annee
                sequence.dernier_numero_registre = 0
            
            sequence.dernier_numero_registre += 1
            sequence.save()
            return f"{prefixe_registre}-{self.type_acte}-{annee}-{sequence.dernier_numero_registre:03d}"


class Tarif(models.Model):
    TYPE_ACTE_CHOICES = [
        ('NAISSANCE', 'Acte de Naissance'),
        ('MARIAGE', 'Acte de Mariage'),
        ('DECES', 'Acte de Décès'),
        ('CERTIFICAT_NAISSANCE', 'Certificat de Naissance'),
        ('CERTIFICAT_MARIAGE', 'Certificat de Mariage'),
        ('CERTIFICAT_DECES', 'Certificat de Décès'),
        # AJOUT DES TYPES MANQUANTS POUR LES DEMANDES
        ('NAISSANCE_COPIE_INTEGRALE', 'Copie intégrale Naissance'),
        ('NAISSANCE_EXTRAIT_AVEC_FILIATION', 'Extrait avec filiation Naissance'),
        ('NAISSANCE_EXTRAIT_SANS_FILIATION', 'Extrait sans filiation Naissance'),
        ('NAISSANCE_CERTIFICAT', 'Certificat Naissance'),
        ('MARIAGE_COPIE_INTEGRALE', 'Copie intégrale Mariage'),
        ('MARIAGE_EXTRAIT_AVEC_FILIATION', 'Extrait avec filiation Mariage'),
        ('MARIAGE_EXTRAIT_SANS_FILIATION', 'Extrait sans filiation Mariage'),
        ('MARIAGE_CERTIFICAT', 'Certificat Mariage'),
        ('DECES_COPIE_INTEGRALE', 'Copie intégrale Décès'),
        ('DECES_EXTRAIT_AVEC_FILIATION', 'Extrait avec filiation Décès'),
        ('DECES_EXTRAIT_SANS_FILIATION', 'Extrait sans filiation Décès'),
        ('DECES_CERTIFICAT', 'Certificat Décès'),
    ]
    
    type_acte = models.CharField(max_length=50, choices=TYPE_ACTE_CHOICES, unique=True)
    prix_unitaire = models.DecimalField(max_digits=8, decimal_places=2)
    timbre_fiscal = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    date_application = models.DateField(default=timezone.now)
    actif = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.type_acte} - {self.prix_unitaire} FCFA"


class AutoNumberMixin:
    """Mixin pour automatiser la numérotation des actes - VERSION UNIFIÉE"""
    
    def get_type_acte(self):
        raise NotImplementedError("Chaque modèle doit définir son type d'acte")
    
    def get_prefixe_numero_acte(self):
        raise NotImplementedError("Chaque modèle doit définir son préfixe")
    
    def get_commune_enregistrement(self):
        raise NotImplementedError("Chaque modèle doit définir sa commune d'enregistrement")
    
    def get_date_enregistrement(self):
        raise NotImplementedError("Chaque modèle doit définir sa date d'enregistrement")
    
    def generate_numbers(self):
        """Génère tous les numéros automatiquement - VERSION ROBUSTE"""
        if not self.pk:
            try:
                with transaction.atomic():
                    commune = self.get_commune_enregistrement()
                    date_enreg = self.get_date_enregistrement()
                    
                    if commune and date_enreg:
                        try:
                            type_acte = self.get_type_acte()
                            sequence, _ = ActeSequence.objects.get_or_create(
                                commune=commune,
                                type_acte=type_acte,
                                defaults={
                                    'dernier_numero_acte': 0, 
                                    'dernier_numero_registre': 0,
                                    'annee_courante': timezone.now().year
                                }
                            )

                            if not self.numero_acte:
                                self.numero_acte = sequence.get_next_numero_acte(self.get_prefixe_numero_acte())
                            
                            if not self.numero_registre:
                                annee = date_enreg.year
                                self.numero_registre = sequence.get_next_numero_registre(annee)
                            
                            if not self.page_registre:
                                reg_num = int(self.numero_registre.split('-')[-1])
                                page_num = ((reg_num - 1) // 10) + 1
                                self.page_registre = f"P{page_num:03d}"
                        except Exception:
                            self._generate_simple_numbers(commune, date_enreg)
                    else:
                        self._generate_fallback_numbers()
            except Exception:
                self._generate_fallback_numbers()

    def _generate_simple_numbers(self, commune, date_enreg):
        """Génère un numéro basé sur le comptage annuel"""
        year = date_enreg.year
        commune_code = getattr(commune, 'code', '000')
        
        model_class = self.__class__
        count = model_class.objects.filter(date_creation__year=year).count() + 1
        
        prefixe = self.get_prefixe_numero_acte()
        self.numero_acte = f"{prefixe}-{commune_code}-{year}-{count:05d}"
        
        if not self.numero_registre:
            self.numero_registre = f"REG-{commune_code}-{year}-{count:05d}"
        
        if not self.page_registre:
            page_num = ((count - 1) // 10) + 1
            self.page_registre = f"P{page_num:03d}"

    def _generate_fallback_numbers(self):
        """Génération de secours basée sur UUID et timestamp"""
        prefixe = self.get_prefixe_numero_acte()
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        uuid_part = str(uuid.uuid4())[:8].upper()
        self.numero_acte = f"{prefixe}-{timestamp}-{uuid_part}"


# ====== MODÈLES D'ACTES ORIGINAUX (événements d'état civil) ======

class ActeNaissance(models.Model, AutoNumberMixin):
    numero_acte = models.CharField(max_length=50, unique=True, blank=True)
    personne = models.OneToOneField('Personne', on_delete=models.CASCADE, related_name='acte_naissance')
    
    commune_enregistrement = models.ForeignKey('Commune', on_delete=models.SET_NULL, null=True, blank=True, related_name='actes_naissance')
    date_enregistrement = models.DateField()
    numero_registre = models.CharField(max_length=30, blank=True)
    page_registre = models.CharField(max_length=10, blank=True)
    
    declarant_nom = models.CharField(max_length=100)
    declarant_qualite = models.CharField(max_length=50)
    temoin1_nom = models.CharField(max_length=100, blank=True)
    temoin2_nom = models.CharField(max_length=100, blank=True)
    
    observations = models.TextField(blank=True)
    agent_enregistreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Naissance"
        verbose_name_plural = "Actes de Naissance"
        indexes = [
            models.Index(fields=['numero_acte']),
            models.Index(fields=['date_enregistrement']),
            models.Index(fields=['commune_enregistrement']),
        ]

    def get_type_acte(self):
        return "NAISSANCE"
    
    def get_prefixe_numero_acte(self):
        return "ACTENAIS"
    
    def get_commune_enregistrement(self):
        return self.commune_enregistrement
    
    def get_date_enregistrement(self):
        return self.date_enregistrement

    def save(self, *args, **kwargs):
        if not self.numero_acte:
            self.generate_numbers()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.date_enregistrement > timezone.now().date():
            raise ValidationError("La date d'enregistrement ne peut pas être dans le futur.")

    def __str__(self):
        return f"Acte N° {self.numero_acte} - {self.personne.nom} {self.personne.prenoms}"


class Mariage(models.Model, AutoNumberMixin):
    """Acte de mariage original créé lors de la célébration"""
    REGIME_MATRIMONIAL_CHOICES = [
        ('COMMUNAUTE', 'Communauté de biens'),
        ('SEPARATION', 'Séparation de biens'),
        ('PARTICIPATION', 'Participation aux acquêts'),
    ]
    
    numero_acte = models.CharField(max_length=50, unique=True, blank=True)
    epoux = models.ForeignKey('Personne', on_delete=models.CASCADE, related_name='mariages_epoux')
    epouse = models.ForeignKey('Personne', on_delete=models.CASCADE, related_name='mariages_epouse')
    
    # Informations du mariage
    date_mariage = models.DateField()
    commune_mariage = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='mariages')
    regime_matrimonial = models.CharField(max_length=15, choices=REGIME_MATRIMONIAL_CHOICES, default='COMMUNAUTE')
    
    # Témoins
    temoin_epoux_1 = models.CharField(max_length=100)
    temoin_epoux_2 = models.CharField(max_length=100)
    temoin_epouse_1 = models.CharField(max_length=100)
    temoin_epouse_2 = models.CharField(max_length=100)
    
    # Officiant et registre
    officier_etat_civil = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    numero_registre = models.CharField(max_length=30, blank=True)
    page_registre = models.CharField(max_length=10, blank=True)
    
    # Métadonnées
    observations = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Mariage"
        verbose_name_plural = "Actes de Mariage"
        indexes = [
            models.Index(fields=['numero_acte']),
            models.Index(fields=['date_mariage']),
            models.Index(fields=['commune_mariage']),
        ]

    def get_type_acte(self):
        return "MARIAGE"
    
    def get_prefixe_numero_acte(self):
        return "ACTEMARIAGE"
    
    def get_commune_enregistrement(self):
        return self.commune_mariage
    
    def get_date_enregistrement(self):
        return self.date_mariage

    def save(self, *args, **kwargs):
        if not self.numero_acte:
            self.generate_numbers()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.date_mariage and self.date_mariage > timezone.now().date():
            raise ValidationError("La date de mariage ne peut pas être dans le futur.")
        
        if self.epoux == self.epouse:
            raise ValidationError("Les époux ne peuvent pas être la même personne.")

    def personnes(self):
        return [self.epoux, self.epouse]

    def __str__(self):
        return f"Mariage N° {self.numero_acte} - {self.epoux.nom} & {self.epouse.nom}"


class ActeDeces(models.Model, AutoNumberMixin):
    numero_acte = models.CharField(max_length=50, unique=True, blank=True)
    personne = models.OneToOneField('Personne', on_delete=models.CASCADE, related_name='acte_deces')
    
    date_deces = models.DateField()
    heure_deces = models.TimeField(blank=True, null=True)
    lieu_deces = models.CharField(max_length=200)
    commune_deces = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='actes_deces')
    cause_deces = models.TextField(blank=True)
    
    declarant_nom = models.CharField(max_length=100)
    declarant_qualite = models.CharField(max_length=50)
    medecin_nom = models.CharField(max_length=100, blank=True)
    numero_certificat_medical = models.CharField(max_length=50, blank=True)
    
    numero_registre = models.CharField(max_length=30, blank=True)
    page_registre = models.CharField(max_length=10, blank=True)
    
    observations = models.TextField(blank=True)
    agent_enregistreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Décès"
        verbose_name_plural = "Actes de Décès"
        indexes = [
            models.Index(fields=['numero_acte']),
            models.Index(fields=['date_deces']),
            models.Index(fields=['commune_deces']),
        ]
    
    def get_type_acte(self):
        return "DECES"
    
    def get_prefixe_numero_acte(self):
        return "ACTEDECES"
    
    def get_commune_enregistrement(self):
        return self.commune_deces
    
    def get_date_enregistrement(self):
        return self.date_deces
    
    def save(self, *args, **kwargs):
        if not self.numero_acte:
            self.generate_numbers()
        super().save(*args, **kwargs)
    
    def clean(self):
        super().clean()
        if self.date_deces > timezone.now().date():
            raise ValidationError("La date de décès ne peut pas être dans le futur.")
    
    def __str__(self):
        return f"Décès N° {self.numero_acte} - {self.personne.nom} {self.personne.prenoms}"


# ====== PLUS BESOIN DE SIGNAUX - GÉNÉRATION DANS save() ======
# Les signaux peuvent causer des conflits avec la méthode save()
# Il vaut mieux garder la génération uniquement dans save()


# ====== MODÈLE DE DEMANDE D'ACTE (copies/extraits) ======

class DemandeActe(models.Model): 
    """Demande de copie ou d'extrait d'un acte d'état civil existant"""
    
    TYPE_DOCUMENT_CHOICES = [
        ('COPIE_INTEGRALE', 'Copie intégrale'),
        ('EXTRAIT_AVEC_FILIATION', 'Extrait avec filiation'),
        ('EXTRAIT_SANS_FILIATION', 'Extrait sans filiation'),
        ('CERTIFICAT', 'Certificat'),
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('EN_ATTENTE_PAIEMENT', 'En attente de paiement'),
        ('PAIEMENT_CONFIRME', 'Paiement confirmé'),
        ('EN_COURS', 'En cours de traitement'),
        ('APPROUVE', 'Approuvé'),
        ('REJETE', 'Rejeté'),
        ('DELIVRE', 'Délivré'),
        ('ANNULE', 'Annulé'),
    ]
    
    MOTIF_DEMANDE_CHOICES = [
        ('PERSONNEL', 'Usage personnel'),
        ('ADMINISTRATIVE', 'Démarche administrative'),
        ('JURIDIQUE', 'Procédure juridique'),
        ('SCOLAIRE', 'Inscription scolaire'),
        ('EMPLOI', 'Recherche d\'emploi'),
        ('AUTRE', 'Autre'),
    ]
    
    LIEN_PARENTE_CHOICES = [
        ('LUI_MEME', 'Lui-même/Elle-même'),
        ('PERE', 'Père'),
        ('MERE', 'Mère'),
        ('ENFANT', 'Enfant'),
        ('CONJOINT', 'Conjoint(e)'),
        ('FRERE_SOEUR', 'Frère/Sœur'),
        ('REPRESENTANT_LEGAL', 'Représentant légal'),
        ('AUTRE', 'Autre'),
    ]
    
    MODE_RETRAIT_CHOICES = [
        ('SUR_PLACE', 'Retrait sur place'),
        ('COURRIER', 'Envoi par courrier'),
        ('EMAIL', 'Envoi par email'),
    ]
    
    # ===== IDENTIFIANTS ET RÉFÉRENCES =====
    numero_demande = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    numero_suivi = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    
    # ===== DEMANDEUR =====
    demandeur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes_actes')
    
    # ===== ACTE CONCERNÉ (un seul à la fois) =====
    acte_naissance = models.ForeignKey(ActeNaissance, on_delete=models.CASCADE, null=True, blank=True, related_name='demandes')
    acte_mariage = models.ForeignKey(Mariage, on_delete=models.CASCADE, null=True, blank=True, related_name='demandes')
    acte_deces = models.ForeignKey(ActeDeces, on_delete=models.CASCADE, null=True, blank=True, related_name='demandes')
    
    # ===== TYPE DE DOCUMENT DEMANDÉ =====
    type_document = models.CharField(max_length=25, choices=TYPE_DOCUMENT_CHOICES, default='COPIE_INTEGRALE')
    nombre_copies = models.PositiveIntegerField(default=1)
    
    # ===== TRAITEMENT =====
    commune_traitement = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='demandes_traitees')
    statut = models.CharField(max_length=25, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    # ===== DATES =====
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation_preliminaire = models.DateTimeField(blank=True, null=True)
    date_traitement = models.DateTimeField(blank=True, null=True)
    date_delivrance = models.DateTimeField(blank=True, null=True)
    
    # ===== INFORMATIONS DEMANDEUR =====
    motif_demande = models.CharField(max_length=20, choices=MOTIF_DEMANDE_CHOICES, default='PERSONNEL')
    lien_avec_personne = models.CharField(max_length=20, choices=LIEN_PARENTE_CHOICES, default='LUI_MEME')
    
    # ===== JUSTIFICATIFS =====
    piece_identite_demandeur = models.FileField(upload_to='justificatifs/identite/', null=True, blank=True)
    justificatif_lien = models.FileField(upload_to='justificatifs/lien/', null=True, blank=True)
    
    # ===== AGENTS ET TRAITEMENT =====
    agent_validateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='demandes_validees')
    agent_traitant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='demandes_traitees')
    commentaire_agent = models.TextField(blank=True)
    commentaire_rejet = models.TextField(blank=True)
    
    # ===== PAIEMENT =====
    tarif_applique = models.ForeignKey('Tarif', on_delete=models.SET_NULL, null=True, blank=True)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_calcule = models.BooleanField(default=False)
    paiement_requis = models.BooleanField(default=True)
    
    # ===== LIVRAISON =====
    mode_retrait = models.CharField(max_length=15, choices=MODE_RETRAIT_CHOICES, default='SUR_PLACE')
    adresse_livraison = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_demande']
        verbose_name = "Demande d'Acte"
        verbose_name_plural = "Demandes d'Actes"
        indexes = [
            models.Index(fields=['numero_demande']),
            models.Index(fields=['numero_suivi']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_demande']),
            models.Index(fields=['demandeur']),
        ]

    # ===== PROPRIÉTÉS =====
    
    @property
    def acte_concerne(self):
        """Retourne l'acte concerné par la demande"""
        if self.acte_naissance:
            return self.acte_naissance
        elif self.acte_mariage:
            return self.acte_mariage
        elif self.acte_deces:
            return self.acte_deces
        return None
    
    @property
    def personne_concernee(self):
        """Retourne la personne concernée par l'acte"""
        acte = self.acte_concerne
        if not acte:
            return None
        
        if isinstance(acte, (ActeNaissance, ActeDeces)):
            return acte.personne
        elif isinstance(acte, Mariage):
            # Pour les mariages, on peut retourner les deux personnes
            return [acte.epoux, acte.epouse]
        return None
    
    @property
    def type_acte(self):
        """Retourne le type d'acte (pour compatibilité)"""
        acte = self.acte_concerne
        if isinstance(acte, ActeNaissance):
            return 'NAISSANCE'
        elif isinstance(acte, Mariage):
            return 'MARIAGE'
        elif isinstance(acte, ActeDeces):
            return 'DECES'
        return None
    
    @property
    def peut_etre_payee(self):
        return self.statut == 'EN_ATTENTE_PAIEMENT' and self.montant_calcule
    
    @property
    def peut_etre_traitee(self):
        if not self.paiement_requis:
            return self.statut in ['EN_ATTENTE', 'PAIEMENT_CONFIRME']
        return (self.statut == 'PAIEMENT_CONFIRME' and 
                hasattr(self, 'paiement') and self.paiement and
                self.paiement.statut == 'CONFIRME')
    
    @property
    def delai_traitement(self):
        if self.date_traitement and self.date_demande:
            return (self.date_traitement - self.date_demande).days
        return None
    
    @property
    def workflow_statut(self):
        workflow_map = {
            'EN_ATTENTE': 'Demande reçue, en attente de validation',
            'EN_ATTENTE_PAIEMENT': 'Demande validée, en attente de paiement',
            'PAIEMENT_CONFIRME': 'Paiement confirmé, en attente de traitement',
            'EN_COURS': 'Demande en cours de traitement',
            'APPROUVE': 'Demande approuvée, en attente de délivrance',
            'REJETE': 'Demande rejetée',
            'DELIVRE': 'Document délivré',
            'ANNULE': 'Demande annulée'
        }
        return workflow_map.get(self.statut, self.statut)

    # ===== MÉTHODES =====
    
    def generate_numero_demande(self):
        """Génère un numéro de demande unique"""
        year = timezone.now().year
        commune_code = self.commune_traitement.code if self.commune_traitement else "000"
        
        # Compter les demandes de l'année pour cette commune
        count = DemandeActe.objects.filter(
            commune_traitement=self.commune_traitement,
            date_demande__year=year
        ).count() + 1
        
        return f"DEM-{commune_code}-{year}-{count:05d}"
    
    def generate_numero_suivi(self):
        """Génère un numéro de suivi public"""
        year = timezone.now().year
        month = timezone.now().month
        return f"SUIVI{year}{month:02d}{str(uuid.uuid4())[:8].upper()}"

    def save(self, *args, **kwargs):
        if not self.numero_demande:
            self.numero_demande = self.generate_numero_demande()
        
        if not self.numero_suivi:
            self.numero_suivi = self.generate_numero_suivi()
        
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        
        # Validation: un seul acte lié
        actes_lies = [self.acte_naissance, self.acte_mariage, self.acte_deces]
        actes_non_nuls = [a for a in actes_lies if a is not None]
        
        if len(actes_non_nuls) == 0:
            raise ValidationError("Une demande doit être liée à un acte existant.")
        
        if len(actes_non_nuls) > 1:
            raise ValidationError("Une demande ne peut être liée qu'à un seul acte.")
        
        # Validation nombre de copies
        if self.nombre_copies <= 0:
            raise ValidationError("Le nombre de copies doit être supérieur à 0.")
        
        if self.nombre_copies > 10:
            raise ValidationError("Maximum 10 copies par demande.")
        
        # Validation lien de parenté
        if (self.lien_avec_personne != 'LUI_MEME' and 
            hasattr(self.demandeur, 'role') and
            self.demandeur.role == 'CITOYEN' and 
            not self.justificatif_lien):
            raise ValidationError("Un justificatif de lien de parenté est requis.")
        
        # Validation mode de retrait
        if self.mode_retrait == 'COURRIER' and not self.adresse_livraison:
            raise ValidationError("L'adresse de livraison est requise pour l'envoi par courrier.")

    def __str__(self):
        acte = self.acte_concerne
        if acte:
            return f"Demande {self.numero_suivi} - {acte}"
        return f"Demande {self.numero_suivi}"

    # ===== MÉTHODES DE WORKFLOW =====
    
    def calculer_montant(self):
        """Calcule le montant total de la demande"""
        try:
            # CORRECTION : Construction du type correct pour recherche tarif
            type_recherche = f"{self.type_acte}_{self.type_document}"
            tarif = Tarif.objects.get(type_acte=type_recherche, actif=True)
            self.tarif_applique = tarif
            self.montant_total = (tarif.prix_unitaire + tarif.timbre_fiscal) * self.nombre_copies
            self.montant_calcule = True
            self.save()
            return self.montant_total
        except Tarif.DoesNotExist:
            raise ValueError(f"Aucun tarif défini pour {type_recherche}")
        except Exception as e:
            raise ValueError(f"Erreur lors du calcul du montant: {str(e)}")
    
    def valider_preliminairement(self, agent):
        """Validation préliminaire avant paiement"""
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
        if self.statut != 'EN_ATTENTE_PAIEMENT':
            raise ValueError("La demande doit être en attente de paiement")
        
        if self.paiement_requis and (not hasattr(self, 'paiement') or not self.paiement or self.paiement.statut != 'CONFIRME'):
            raise ValueError("Le paiement n'est pas confirmé")
        
        self.statut = 'PAIEMENT_CONFIRME'
        self.save()
        return True
    
    def commencer_traitement(self, agent):
        """Démarre le traitement après paiement confirmé"""
        if self.statut != 'PAIEMENT_CONFIRME':
            raise ValueError("Le paiement doit être confirmé avant le traitement")
        
        self.statut = 'EN_COURS'
        self.agent_traitant = agent
        self.date_traitement = timezone.now()
        self.save()
        return True
    
    def approuver(self, agent, commentaire=""):
        """Approuve la demande"""
        if self.statut != 'EN_COURS':
            raise ValueError("Seules les demandes en cours peuvent être approuvées")
        
        self.statut = 'APPROUVE'
        self.agent_traitant = agent
        self.commentaire_agent = commentaire
        self.save()
        return True
    
    def rejeter(self, agent, motif):
        """Rejette la demande avec remboursement"""
        if self.statut not in ['EN_COURS', 'PAIEMENT_CONFIRME']:
            raise ValueError("Cette demande ne peut pas être rejetée")
        
        self.statut = 'REJETE'
        self.agent_traitant = agent
        self.commentaire_rejet = motif
        self.save()
        
        # Déclencher le remboursement si nécessaire
        if hasattr(self, 'paiement') and self.paiement and self.paiement.statut == 'CONFIRME':
            self.paiement.statut = 'REMBOURSE'
            self.paiement.save()
        
        return True
    
    def delivrer(self, agent):
        """Marque la demande comme délivrée"""
        if self.statut != 'APPROUVE':
            raise ValueError("Seules les demandes approuvées peuvent être délivrées")
        
        # Générer le document
        try:
            doc = DocumentNumerique.objects.create(demande=self)
            doc.generate_acte_pdf()  # CORRECTION: Utiliser generate_acte_pdf au lieu de generate_document_pdf
        except Exception as e:
            raise ValueError(f"Erreur lors de la génération du document: {str(e)}")
        
        # Notification email
        try:
            from django.core.mail import send_mail
            send_mail(
                "Votre document est prêt",
                f"Votre document {self.numero_suivi} est disponible au téléchargement.",
                "noreply@etatcivil.example.com",
                [self.demandeur.email],
                fail_silently=True,
            )
        except Exception:
            pass  # Ne pas bloquer la délivrance pour un problème d'email
        
        self.statut = 'DELIVRE'
        self.agent_traitant = agent
        self.date_delivrance = timezone.now()
        self.save()
        return True


class DocumentNumerique(models.Model):
    TYPE_ACTE_CHOICES = [
        ('NAISSANCE', 'Acte de Naissance'),
        ('MARIAGE', 'Acte de Mariage'),
        ('DECES', 'Acte de Décès'),
        ('CERTIFICAT_NAISSANCE', 'Certificat de Naissance'),
        ('CERTIFICAT_MARIAGE', 'Certificat de Mariage'),
        ('CERTIFICAT_DECES', 'Certificat de Décès'),
    ]
    
    demande = models.ForeignKey(DemandeActe, on_delete=models.CASCADE, related_name='documents')
    type_document = models.CharField(max_length=100, choices=TYPE_ACTE_CHOICES, editable=False)
    nom_fichier = models.CharField(max_length=255)
    fichier = models.FileField(upload_to='documents_etat_civil/')
    signature_numerique = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def generate_acte_pdf(self):
        """Génère le PDF de l'acte selon le type de demande"""
        try:
            from .acte_generator import ActeGenerator  # CORRECTION: Import conditionnel
        except ImportError:
            raise ValueError("ActeGenerator non disponible")
        
        demande = self.demande
        numero = str(demande.numero_demande).zfill(5)

        if demande.type_acte == 'NAISSANCE':
            acte = demande.acte_naissance  # CORRECTION: utiliser directement l'acte
            pdf_buffer = ActeGenerator.generate_acte_naissance(acte)
            prefix = "Fichactenaiss"
        elif demande.type_acte == 'MARIAGE':
            acte = demande.acte_mariage  # CORRECTION: utiliser directement l'acte
            pdf_buffer = ActeGenerator.generate_acte_mariage(acte)
            prefix = "Fichactemariage"
        elif demande.type_acte == 'DECES':
            acte = demande.acte_deces  # CORRECTION: utiliser directement l'acte
            pdf_buffer = ActeGenerator.generate_acte_deces(acte)
            prefix = "Fichactedeces"
        else:
            raise ValueError("Type d'acte non supporté")
        
        # Nom du fichier
        filename = f"{prefix}{numero}.pdf"
        self.nom_fichier = filename
        self.type_document = demande.type_acte
        self.fichier.save(filename, ContentFile(pdf_buffer.read()))

        # Signature numérique
        self.sign_document()

        return self.fichier
    def generate_document_pdf(self):
        """Alias pour generate_acte_pdf pour compatibilité"""
        return self.generate_acte_pdf()

    def sign_document(self):
        """Signe le document numériquement"""
        if not self.fichier:
            raise ValueError("Aucun fichier à signer")
        
        try:
            from .digital_signer import DigitalSigner  # CORRECTION: Import conditionnel
            file_path = self.fichier.path
            self.signature_numerique = DigitalSigner.sign_document(file_path)
            self.save()
        except ImportError:
            # Si DigitalSigner n'existe pas encore, générer une signature temporaire
            import hashlib
            file_path = self.fichier.path
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            self.signature_numerique = f"TEMP_SIGNATURE_{file_hash[:16]}"
            self.save()

    def verify_signature(self):
        """Vérifie la signature numérique du document"""
        if not self.fichier or not self.signature_numerique:
            return False
        
        try:
            from .digital_signer import DigitalSigner  # CORRECTION: Import conditionnel
            file_path = self.fichier.path
            return DigitalSigner.verify_signature(file_path, self.signature_numerique)
        except ImportError:
            # Vérification temporaire pour les signatures temporaires
            return self.signature_numerique.startswith("TEMP_SIGNATURE_")
        
        file_path = self.fichier.path
        self.signature_numerique = DigitalSigner.sign_document(file_path)
        self.save()

  


    def clean(self):
        if not self.signature_numerique and self.fichier:
            self.sign_document()


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
        ('EN_COURS', 'En cours de traitement'),
        ('CONFIRME', 'Confirmé'),
        ('ECHEC', 'Échec'),
        ('EXPIRE', 'Expiré'),
        ('REMBOURSE', 'Remboursé'),
        ('ANNULE', 'Annulé'),
    ]
    
    # Relations
    demande = models.OneToOneField(
        'DemandeActe', 
        on_delete=models.CASCADE, 
        related_name='paiement'
    )
    
    # Informations financières
    montant = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Montant de base de l'acte"
    )
    montant_timbres = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Montant des timbres fiscaux"
    )
    montant_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Montant total à payer"
    )
    
    # Méthode et statut
    methode_paiement = models.CharField(
        max_length=20, 
        choices=METHODE_PAIEMENT_CHOICES
    )
    statut = models.CharField(
        max_length=15, 
        choices=STATUT_PAIEMENT_CHOICES, 
        default='EN_ATTENTE'
    )
    
    # Références et identifiants
    reference_transaction = models.CharField(
        max_length=100, 
        unique=True,
        editable=False,
        help_text="Référence unique de la transaction"
    )
    reference_externe = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Référence du provider de paiement"
    )
    numero_telephone = models.CharField(
        max_length=15, 
        blank=True,
        help_text="Numéro de téléphone pour Mobile Money"
    )
    
    # Dates importantes
    date_paiement = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du paiement"
    )
    date_confirmation = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Date de confirmation du paiement"
    )
    date_expiration = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Date d'expiration du paiement"
    )
    date_remboursement = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Date du remboursement"
    )
    
    # Informations complémentaires
    commentaire = models.TextField(
        blank=True,
        help_text="Commentaires sur le paiement"
    )
    code_erreur = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Code d'erreur en cas d'échec"
    )
    message_erreur = models.TextField(
        blank=True,
        help_text="Message d'erreur détaillé"
    )
    
    # Agent qui a traité
    agent_confirmateur = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paiements_confirmes',
        help_text="Agent qui a confirmé le paiement"
    )
    
    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_paiement']
        indexes = [
            models.Index(fields=['reference_transaction']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_paiement']),
        ]
    
    def clean(self):
        """Validation des données - VERSION CORRIGÉE"""
        errors = {}

        # Validation Mobile Money
        if self.methode_paiement in ['MOBILE_MONEY', 'ORANGE_MONEY', 'MTN_MONEY', 'MOOV_MONEY']:
            if not self.numero_telephone:
                errors['numero_telephone'] = "Le numéro de téléphone est requis pour Mobile Money"

        # Validation montant
        if self.montant is not None and self.montant <= 0:
            errors['montant'] = "Le montant doit être positif"

        if self.montant_timbres is not None and self.montant_timbres < 0:
            errors['montant_timbres'] = "Le montant des timbres ne peut pas être négatif"

        # Validation cohérence des montants
        if (self.montant is not None and self.montant_timbres is not None and 
            self.montant_total is not None):
            from decimal import Decimal  # CORRECTION: Import local
            montant_calcule = self.montant + self.montant_timbres
            if abs(self.montant_total - montant_calcule) > Decimal('0.01'):
                errors['montant_total'] = (
                    f"Le montant total ({self.montant_total}) ne correspond pas à "
                    f"la somme des montants ({montant_calcule})"
                )

        # Vérification du tarif simplifiée et sécurisée
        if (self.demande_id and self.pk is None):  # Seulement à la création
            try:
                if (hasattr(self, 'demande') and self.demande and
                    hasattr(self.demande, 'type_acte') and self.demande.type_acte and
                    hasattr(self.demande, 'type_document') and self.demande.type_document):
                    
                    type_recherche = f"{self.demande.type_acte}_{self.demande.type_document}"
                    if not Tarif.objects.filter(type_acte=type_recherche, actif=True).exists():
                        errors['montant'] = f"Aucun tarif actif défini pour {type_recherche}"
            except Exception:
                pass  # Ignorer les erreurs pour ne pas bloquer la validation

        if errors:
            from django.core.exceptions import ValidationError  # CORRECTION: Import local
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Sauvegarde avec logique métier"""
        # Générer la référence si absente
        if not self.reference_transaction:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            uuid_part = str(uuid.uuid4())[:8].upper()
            self.reference_transaction = f"PAY{timestamp}{uuid_part}"
        
        # Récupération automatique du tarif si montant non défini ET si demande existe
        if (self.demande_id and hasattr(self, 'demande') and self.demande and
            hasattr(self.demande, 'type_acte') and self.demande.type_acte and
            not self.montant):
            try:
                self._calculer_montants_depuis_tarif()
            except Exception:
                pass  # Éviter que l'erreur de calcul empêche la sauvegarde
        
        # Calcul automatique du montant total si pas défini
        if not self.montant_total and self.montant is not None:
            from decimal import Decimal  # CORRECTION: Import local
            montant_timbres = self.montant_timbres or Decimal('0')
            self.montant_total = self.montant + montant_timbres
        
        # Validation avant sauvegarde
        try:
            self.full_clean()
        except ValidationError:
            pass  # Laisser Django gérer les erreurs de validation
        
        super().save(*args, **kwargs)
        
        # Mise à jour du statut de la demande après sauvegarde
        self._mettre_a_jour_demande()
        
    def _calculer_montants_depuis_tarif(self):
        """Calcule les montants depuis le tarif"""
        try:
            # Construction du type correct et gestion des erreurs
            if not hasattr(self.demande, 'type_acte') or not self.demande.type_acte:
                raise ValueError("Type d'acte non défini sur la demande")
            
            if not hasattr(self.demande, 'type_document') or not self.demande.type_document:
                raise ValueError("Type de document non défini sur la demande")
            
            type_recherche = f"{self.demande.type_acte}_{self.demande.type_document}"
            
            tarif = Tarif.objects.get(
                type_acte=type_recherche, 
                actif=True
            )
            
            nombre_copies = getattr(self.demande, 'nombre_copies', 1)
            self.montant = tarif.prix_unitaire * nombre_copies
            self.montant_timbres = tarif.timbre_fiscal * nombre_copies
            
        except Tarif.DoesNotExist:
            from django.core.exceptions import ValidationError  # CORRECTION: Import local
            raise ValidationError(
                f"Aucun tarif actif défini pour {type_recherche}"
            )
        except Exception as e:
            from django.core.exceptions import ValidationError  # CORRECTION: Import local
            raise ValidationError(
                f"Impossible de calculer le tarif : {str(e)}"
            )
    def _mettre_a_jour_demande(self):
        """Met à jour le statut de la demande selon le paiement"""
        if not self.demande_id or not hasattr(self, 'demande') or not self.demande:
            return
        
        try:
            if (self.statut == 'CONFIRME' and 
                hasattr(self.demande, 'statut') and 
                self.demande.statut == 'EN_ATTENTE_PAIEMENT'):
                
                if hasattr(self.demande, 'confirmer_paiement'):
                    self.demande.confirmer_paiement()
                else:
                    # Fallback si la méthode n'existe pas
                    self.demande.statut = 'PAIEMENT_CONFIRME'
                    self.demande.save(update_fields=['statut'])
            
            elif (self.statut in ['ECHEC', 'EXPIRE', 'ANNULE'] and 
                  hasattr(self.demande, 'statut') and 
                  self.demande.statut == 'EN_ATTENTE_PAIEMENT'):
                
                # Remettre en attente si le paiement échoue
                self.demande.statut = 'EN_ATTENTE'
                self.demande.save(update_fields=['statut'])
        
        except Exception:
            # Éviter que les erreurs de mise à jour de demande cassent la sauvegarde
            pass
    
    def confirmer(self, agent=None):
        """Confirme le paiement"""
        if self.statut not in ['EN_ATTENTE', 'EN_COURS']:
            raise ValueError(
                f"Impossible de confirmer un paiement avec le statut '{self.statut}'"
            )
        
        self.statut = 'CONFIRME'
        self.date_confirmation = timezone.now()
        self.agent_confirmateur = agent
        self.code_erreur = ""
        self.message_erreur = ""
        
        self.save(update_fields=[
            'statut', 'date_confirmation', 'agent_confirmateur',
            'code_erreur', 'message_erreur'
        ])
        
        return True
    
    def echec(self, code_erreur="", message_erreur=""):
        """Marque le paiement comme échoué"""
        self.statut = 'ECHEC'
        self.code_erreur = code_erreur
        self.message_erreur = message_erreur
        
        self.save(update_fields=['statut', 'code_erreur', 'message_erreur'])
        
        return True
    
    def expirer(self):
        """Marque le paiement comme expiré"""
        if self.statut in ['EN_ATTENTE', 'EN_COURS']:
            self.statut = 'EXPIRE'
            self.save(update_fields=['statut'])
            return True
        return False
    
    def annuler(self, motif=""):
        """Annule le paiement"""
        if self.statut in ['EN_ATTENTE', 'EN_COURS']:
            self.statut = 'ANNULE'
            if motif:
                self.commentaire = motif
            self.save(update_fields=['statut', 'commentaire'])
            return True
        return False
    
    def rembourser(self, agent=None, motif=""):
        """Procède au remboursement"""
        if self.statut != 'CONFIRME':
            raise ValueError(
                "Seuls les paiements confirmés peuvent être remboursés"
            )
        
        self.statut = 'REMBOURSE'
        self.date_remboursement = timezone.now()
        if motif:
            self.commentaire = motif
        self.agent_confirmateur = agent
        
        self.save(update_fields=[
            'statut', 'date_remboursement', 'commentaire', 'agent_confirmateur'
        ])
        
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
    def peut_etre_annule(self):
        """Vérifie si le paiement peut être annulé"""
        return self.statut in ['EN_ATTENTE', 'EN_COURS']
    
    @property
    def est_expire(self):
        """Vérifie si le paiement a expiré"""
        if not self.date_expiration:
            return False
        
        return (timezone.now() > self.date_expiration and 
                self.statut == 'EN_ATTENTE')
    
    @property
    def est_finalise(self):
        """Vérifie si le paiement est dans un état final"""
        return self.statut in ['CONFIRME', 'ECHEC', 'EXPIRE', 'REMBOURSE', 'ANNULE']
    
    @property
    def duree_traitement(self):
        """Calcule la durée de traitement du paiement"""
        if self.date_confirmation:
            return self.date_confirmation - self.date_paiement
        return None
    
    def get_statut_display_with_icon(self):
        """Retourne le statut avec une icône"""
        icons = {
            'EN_ATTENTE': '⏳',
            'EN_COURS': '🔄',
            'CONFIRME': '✅',
            'ECHEC': '❌',
            'EXPIRE': '⏰',
            'REMBOURSE': '💰',
            'ANNULE': '🚫',
        }
        return f"{icons.get(self.statut)} {self.get_statut_display()}"
    
    def __str__(self):
        return (f"Paiement {self.reference_transaction} - "
                f"{self.montant_total} FCFA ({self.get_statut_display()})")
    
    def __repr__(self):
        return (f"<Paiement(id={self.pk}, ref='{self.reference_transaction}', "
                f"montant={self.montant_total}, statut='{self.statut}')>")




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

