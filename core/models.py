from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
import uuid
from datetime import date
from .acte_generator import ActeGenerator
from .digital_signer import DigitalSigner
from django.db import models
import os
from django.core.files.base import ContentFile
from django.contrib import messages
# Modèle utilisateur personnalisé
import uuid
from .services.payment_service import CinetPayService
from django.utils.crypto import get_random_string
from django.db import IntegrityError

# Signaux pour s'assurer de la génération automatique
from django.db.models.signals import pre_save
from django.dispatch import receiver
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models, transaction
from django.core.exceptions import ValidationError
from datetime import datetime
from django.apps import apps
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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
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
    
    @classmethod
    def detecter_doublon(cls, nom, prenoms, date_naissance, lieu_naissance):
        return cls.objects.filter(
            nom__iexact=nom,
            prenoms__iexact=prenoms,
            date_naissance=date_naissance,
            lieu_naissance__iexact=lieu_naissance
        ).exists()

    def __str__(self):
        return f"{self.nom} {self.prenoms}"






class ActeSequence(models.Model):
    """Modèle pour suivre les séquences de numérotation par commune et par type d'acte"""
    commune = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='sequences_actes')
    type_acte = models.CharField(max_length=20)  # 'NAISSANCE', 'MARIAGE', 'DECES'
    dernier_numero_acte = models.IntegerField(default=0)
    dernier_numero_registre = models.IntegerField(default=0)
    dernier_numero_demande = models.IntegerField(default=0)
    annee_courante = models.IntegerField(default=datetime.now().year)
    
    class Meta:
        unique_together = ['commune', 'type_acte']
        verbose_name = "Séquence d'Acte"
        verbose_name_plural = "Séquences d'Actes"

    def __str__(self):
        return f"Séquence {self.commune} - {self.type_acte}: {self.dernier_numero_acte}"

    def get_next_numero_acte(self, annee):
        """Obtient le prochain numéro d'acte de façon thread-safe"""
        with transaction.atomic():
            # Recharger l'objet depuis la base pour éviter les conditions de course
            sequence = ActeSequence.objects.select_for_update().get(pk=self.pk)
            
            # Réinitialiser le compteur si on change d'année
            if sequence.annee_courante != annee:
                sequence.annee_courante = annee
                sequence.dernier_numero_acte = 0
            
            sequence.dernier_numero_acte += 1
            sequence.save(update_fields=['dernier_numero_acte', 'annee_courante'])
            
            if self.type_acte == 'NAISSANCE':
                return f"ACTENAISS{annee}{sequence.dernier_numero_acte:05d}"
            elif self.type_acte == 'MARIAGE':
                return f"ACTEMARIAGE{annee}{sequence.dernier_numero_acte:05d}"
            elif self.type_acte == 'DECES':
                return f"ACTEDECES{annee}{sequence.dernier_numero_acte:05d}"
            else:
                return f"ACTE{self.type_acte}{annee}{sequence.dernier_numero_acte:05d}"

    def get_next_numero_demande(self, type_demande, personne_concernee=None, epoux=None, epouse=None):
        """Obtient le prochain numéro de demande de façon thread-safe"""
        with transaction.atomic():
            sequence = ActeSequence.objects.select_for_update().get(pk=self.pk)
            sequence.dernier_numero_demande += 1
            sequence.save(update_fields=['dernier_numero_demande'])
            
            if type_demande in ['NAISSANCE', 'CERTIFICAT_NAISSANCE']:
                return f"DEMACTENAISS{sequence.dernier_numero_demande:06d}"
            elif type_demande in ['MARIAGE', 'CERTIFICAT_MARIAGE']:
                if epoux and epouse:
                    lettres_epoux = epoux.nom[:2].upper() if len(epoux.nom) >= 2 else epoux.nom.upper().ljust(2, 'X')
                    lettres_epouse = epouse.nom[:2].upper() if len(epouse.nom) >= 2 else epouse.nom.upper().ljust(2, 'X')
                    return f"DEMACTEMARIAGE{lettres_epoux}{lettres_epouse}{sequence.dernier_numero_demande:06d}"
                return f"DEMACTEMARIAGE{sequence.dernier_numero_demande:06d}"
            elif type_demande in ['DECES', 'CERTIFICAT_DECES']:
                if personne_concernee:
                    lettres_defunt = personne_concernee.nom[:3].upper() if len(personne_concernee.nom) >= 3 else personne_concernee.nom.upper().ljust(3, 'X')
                    return f"DEMACTEDECES{lettres_defunt}{sequence.dernier_numero_demande:06d}"
                return f"DEMACTEDECES{sequence.dernier_numero_demande:06d}"

    def get_next_numero_registre(self, annee, prefixe_registre="REG"):
        """Obtient le prochain numéro de registre de façon thread-safe"""
        with transaction.atomic():
            sequence = ActeSequence.objects.select_for_update().get(pk=self.pk)
            
            if sequence.annee_courante != annee:
                sequence.annee_courante = annee
                sequence.dernier_numero_registre = 0
            
            sequence.dernier_numero_registre += 1
            sequence.save(update_fields=['dernier_numero_registre', 'annee_courante'])
            return f"{prefixe_registre}-{self.type_acte}-{annee}-{sequence.dernier_numero_registre:03d}"


class AutoNumberMixin:
    """Mixin pour automatiser la numérotation des actes avec gestion d'erreurs améliorée"""
    
    def get_type_acte(self):
        raise NotImplementedError("Chaque modèle doit définir son type d'acte")
    
    def get_commune_enregistrement(self):
        raise NotImplementedError("Chaque modèle doit définir sa commune d'enregistrement")
    
    def get_date_enregistrement(self):
        raise NotImplementedError("Chaque modèle doit définir sa date d'enregistrement")

    def generate_numbers(self, force=False):
        """Génère tous les numéros automatiquement avec gestion d'erreurs"""
        if self.pk and not force:  # Éviter de régénérer pour les objets existants
            return
            
        commune = self.get_commune_enregistrement()
        if not commune:
            raise ValidationError("La commune d'enregistrement est requise")
            
        type_acte = self.get_type_acte()
        date_enreg = self.get_date_enregistrement()
        
        if not date_enreg:
            raise ValidationError("La date d'enregistrement est requise")
            
        annee = date_enreg.year
        
        with transaction.atomic():
            sequence, created = ActeSequence.objects.select_for_update().get_or_create(
                commune=commune,
                type_acte=type_acte,
                defaults={
                    'dernier_numero_acte': 0, 
                    'dernier_numero_registre': 0,
                    'dernier_numero_demande': 0,
                    'annee_courante': annee
                }
            )
            
            # Générer le numéro d'acte seulement s'il n'existe pas
            if not self.numero_acte:
                self.numero_acte = sequence.get_next_numero_acte(annee)
            
            # Générer le numéro de registre seulement s'il n'existe pas
            if not self.numero_registre:
                self.numero_registre = sequence.get_next_numero_registre(annee)
            
            # Générer la page de registre seulement si elle n'existe pas
            if not self.page_registre and self.numero_registre:
                try:
                    reg_num = int(self.numero_registre.split('-')[-1])
                    page_num = ((reg_num - 1) // 10) + 1
                    self.page_registre = f"P{page_num:03d}"
                except (ValueError, IndexError):
                    self.page_registre = "P001"


class ActeNaissance(models.Model, AutoNumberMixin):
    numero_acte = models.CharField(max_length=50, unique=True, blank=True)
    personne = models.OneToOneField('Personne', on_delete=models.CASCADE, related_name='acte_naissance')
    commune_enregistrement = models.ForeignKey('Commune', on_delete=models.SET_NULL, null=True, blank=True, related_name='actes_naissance')
    date_enregistrement = models.DateField()
    numero_registre = models.CharField(max_length=30, blank=True)
    page_registre = models.CharField(max_length=10, blank=True)
    declarant_nom = models.CharField(max_length=100)
    declarant_qualite = models.CharField(max_length=50)  # père, mère, témoin, etc.
    temoin1_nom = models.CharField(max_length=100, blank=True)
    temoin2_nom = models.CharField(max_length=100, blank=True)
    observations = models.TextField(blank=True)
    agent_enregistreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Naissance"
        verbose_name_plural = "Actes de Naissance"

    def get_type_acte(self):
        return "NAISSANCE"
    
    def get_commune_enregistrement(self):
        return self.commune_enregistrement
    
    def get_date_enregistrement(self):
        return self.date_enregistrement

    def save(self, *args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with transaction.atomic():
                    # Générer les numéros si nécessaire
                    if not self.numero_acte:
                        self.generate_numbers()
                    
                    super().save(*args, **kwargs)
                    break  # Succès, sortir de la boucle
                    
            except Exception as e:
                error_str = str(e).lower()
                if 'unique' in error_str and 'numero_acte' in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Forcer la régénération du numéro
                        self.numero_acte = ""
                        self.generate_numbers(force=True)
                    else:
                        # Dernière tentative avec un UUID
                        short_uuid = str(uuid.uuid4())[:8].upper()
                        annee = self.date_enregistrement.year if self.date_enregistrement else datetime.now().year
                        self.numero_acte = f"ACTENAISS{annee}{short_uuid}"
                        super().save(*args, **kwargs)
                        break
                else:
                    raise  # Relancer l'erreur si ce n'est pas un problème d'unicité

    def clean(self):
        if self.date_enregistrement and self.date_enregistrement > datetime.now().date():
            raise ValidationError("La date d'enregistrement ne peut pas être dans le futur.")
        
        if not self.commune_enregistrement:
            raise ValidationError("La commune d'enregistrement est requise.")
        
        # Vérifier l'unicité du numéro d'acte seulement s'il est défini
        if self.numero_acte and ActeNaissance.objects.filter(
            numero_acte=self.numero_acte
        ).exclude(pk=self.pk).exists():
            raise ValidationError("Ce numéro d'acte existe déjà.")

    def __str__(self):
        return f"Acte N° {self.numero_acte or 'En cours'} - {self.personne.nom} {self.personne.prenoms}"


class Mariage(models.Model, AutoNumberMixin):
    REGIME_MATRIMONIAL_CHOICES = [
        ('COMMUNAUTE', 'Communauté de biens'),
        ('SEPARATION', 'Séparation de biens'),
        ('PARTICIPATION', 'Participation aux acquêts'),
    ]
    
    numero_acte = models.CharField(max_length=50, unique=True, blank=True)
    epoux = models.ForeignKey('Personne', on_delete=models.CASCADE, related_name='mariages_epoux')
    epouse = models.ForeignKey('Personne', on_delete=models.CASCADE, related_name='mariages_epouse')
    date_mariage = models.DateField()
    commune_mariage = models.ForeignKey('Commune', on_delete=models.CASCADE, related_name='mariages')
    regime_matrimonial = models.CharField(max_length=15, choices=REGIME_MATRIMONIAL_CHOICES, default='COMMUNAUTE')
    temoin_epoux_1 = models.CharField(max_length=100)
    temoin_epoux_2 = models.CharField(max_length=100)
    temoin_epouse_1 = models.CharField(max_length=100)
    temoin_epouse_2 = models.CharField(max_length=100)
    officier_etat_civil = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    numero_registre = models.CharField(max_length=30, blank=True)
    page_registre = models.CharField(max_length=10, blank=True)
    observations = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Mariage"
        verbose_name_plural = "Actes de Mariage"

    def get_type_acte(self):
        return "MARIAGE"
    
    def get_commune_enregistrement(self):
        return self.commune_mariage
    
    def get_date_enregistrement(self):
        return self.date_mariage

    def save(self, *args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with transaction.atomic():
                    if not self.numero_acte:
                        self.generate_numbers()
                    super().save(*args, **kwargs)
                    break
                    
            except Exception as e:
                error_str = str(e).lower()
                if 'unique' in error_str and 'numero_acte' in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.numero_acte = ""
                        self.generate_numbers(force=True)
                    else:
                        short_uuid = str(uuid.uuid4())[:8].upper()
                        annee = self.date_mariage.year if self.date_mariage else datetime.now().year
                        self.numero_acte = f"ACTEMARIAGE{annee}{short_uuid}"
                        super().save(*args, **kwargs)
                        break
                else:
                    raise

    def clean(self):
        super().clean()
        if self.date_mariage and self.date_mariage > datetime.now().date():
            raise ValidationError("La date de mariage ne peut pas être dans le futur.")
        
        # Vérifier que les époux ne sont pas la même personne
        if self.epoux == self.epouse:
            raise ValidationError("Les époux ne peuvent pas être la même personne.")

        if hasattr(self.epoux, 'situation_matrimoniale') and self.epoux.situation_matrimoniale != 'CELIBATAIRE':
            raise ValidationError("L'époux n'est pas célibataire.")

        if hasattr(self.epouse, 'situation_matrimoniale') and self.epouse.situation_matrimoniale != 'CELIBATAIRE':
            raise ValidationError("L'épouse n'est pas célibataire.")

    def personnes(self):
        return [self.epoux, self.epouse]

    def __str__(self):
        return f"Mariage N° {self.numero_acte or 'En cours'} - {self.epoux.nom} & {self.epouse.nom}"


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

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Acte de Décès"
        verbose_name_plural = "Actes de Décès"

    def get_type_acte(self):
        return "DECES"
    
    def get_commune_enregistrement(self):
        return self.commune_deces
    
    def get_date_enregistrement(self):
        return self.date_deces

    def save(self, *args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with transaction.atomic():
                    if not self.numero_acte:
                        self.generate_numbers()
                    super().save(*args, **kwargs)
                    break
                    
            except Exception as e:
                error_str = str(e).lower()
                if 'unique' in error_str and 'numero_acte' in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.numero_acte = ""
                        self.generate_numbers(force=True)
                    else:
                        short_uuid = str(uuid.uuid4())[:8].upper()
                        annee = self.date_deces.year if self.date_deces else datetime.now().year
                        self.numero_acte = f"ACTEDECES{annee}{short_uuid}"
                        super().save(*args, **kwargs)
                        break
                else:
                    raise

    def clean(self):
        super().clean()
        if self.date_deces and self.date_deces > datetime.now().date():
            raise ValidationError("La date de décès ne peut pas être dans le futur.")

    def __str__(self):
        return f"Décès N° {self.numero_acte or 'En cours'} - {self.personne.nom} {self.personne.prenoms}"


# Le reste de vos modèles (Tarif, DemandeActe) reste identique
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
    
    def clean(self):
        if self.prix_unitaire < 0:
            raise ValidationError("Le prix unitaire ne peut pas être négatif.")
        if self.timbre_fiscal < 0:
            raise ValidationError("Le timbre fiscal ne peut pas être négatif.")

    def __str__(self):
        return f"{self.type_acte} - {self.prix_unitaire} FCFA"



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
    
    # Champs de base
    numero_demande = models.CharField(max_length=50, unique=True, blank=True)
    demandeur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes')
    type_acte = models.CharField(max_length=100, choices=TYPE_ACTE_CHOICES)
    tarif_applique = models.ForeignKey('Tarif', on_delete=models.SET_NULL, null=True, blank=True)
    personne_concernee = models.ForeignKey('Personne', on_delete=models.CASCADE, related_name='demandes_actes')
    statut = models.CharField(max_length=25, choices=STATUT_CHOICES, default='EN_ATTENTE')
    commune_traitement = models.ForeignKey('Commune', on_delete=models.CASCADE)
    nombre_copies = models.PositiveIntegerField(default=1)
    
    # Ajout d'un champ pour indiquer si le montant a été calculé
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_calcule = models.BooleanField(default=False)
    paiement_requis = models.BooleanField(default=True)
    
    # Dates importantes
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation_preliminaire = models.DateTimeField(blank=True, null=True)
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
        max_length=30,
        unique=True,
        blank=True,
        verbose_name="Numéro de suivi public"
    )

    def __str__(self):
        return self.numero_demande or f"Demande #{self.pk}"
    
    def generate_numero_demande(self):
        """Génère le numéro de demande selon le type avec gestion d'erreurs"""
        if self.numero_demande or not self.commune_traitement:
            return  # Déjà généré ou pas de commune
            
        try:
            # Déterminer le type d'acte pour la séquence
            if self.type_acte in ['NAISSANCE', 'CERTIFICAT_NAISSANCE']:
                type_sequence = 'NAISSANCE'
            elif self.type_acte in ['MARIAGE', 'CERTIFICAT_MARIAGE']:
                type_sequence = 'MARIAGE'
            elif self.type_acte in ['DECES', 'CERTIFICAT_DECES']:
                type_sequence = 'DECES'
            else:
                type_sequence = 'NAISSANCE'  # Par défaut
            
            # Créer ou récupérer la séquence
            sequence, created = ActeSequence.objects.get_or_create(
                commune=self.commune_traitement,
                type_acte=type_sequence,
                defaults={
                    'dernier_numero_acte': 0, 
                    'dernier_numero_registre': 0,
                    'dernier_numero_demande': 0,
                    'annee_courante': datetime.now().year
                }
            )
            
            # Pour les mariages, récupérer les informations des époux
            epoux = None
            epouse = None
            if self.type_acte in ['MARIAGE', 'CERTIFICAT_MARIAGE']:
                try:
                    mariage = (self.personne_concernee.mariages_epoux.first() or 
                              self.personne_concernee.mariages_epouse.first())
                    if mariage:
                        epoux = mariage.epoux
                        epouse = mariage.epouse
                except:
                    pass
            
            # Générer le numéro via la séquence
            self.numero_demande = sequence.get_next_numero_demande(
                self.type_acte, 
                self.personne_concernee,
                epoux,
                epouse
            )
            
        except Exception as e:
            # En cas d'erreur, générer un numéro de base
            year = datetime.now().year
            month = datetime.now().month
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.numero_demande = f"DEM{year}{month:02d}{short_uuid}"

    def clean(self):
        if self.nombre_copies <= 0:
            raise ValidationError("Le nombre de copies doit être supérieur à 0")
        
        if self.nombre_copies > 10:
            raise ValidationError("Maximum 10 copies par demande")
        
        # Validation du lien de parenté
        if (self.lien_avec_personne != 'LUI_MEME' and 
            hasattr(self, 'demandeur') and hasattr(self.demandeur, 'role') and
            self.demandeur.role == 'CITOYEN' and 
            not self.justificatif_lien):
            raise ValidationError(
                "Un justificatif de lien de parenté est requis"
            )
        
        # Validation mode de retrait
        if self.mode_retrait == 'COURRIER' and not self.adresse_livraison:
            raise ValidationError(
                "L'adresse de livraison est requise pour l'envoi par courrier"
            )

    def save(self, *args, **kwargs):
        # Générer le numéro de demande si absent
        if not self.numero_demande:
            self.generate_numero_demande()

        # Générer le numéro de suivi si absent
        if not self.numero_suivi:
            year = datetime.now().year
            month = datetime.now().month
            while True:
                code = get_random_string(length=6).upper()
                numero = f"DEM{year}{month:02d}{code}"
                if not DemandeActe.objects.filter(numero_suivi=numero).exists():
                    self.numero_suivi = numero
                    break

        # Sauvegarde effective
        super().save(*args, **kwargs)
    class Meta:
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['date_demande']),
            models.Index(fields=['commune_traitement', 'statut']),
        ]
    # Le reste de vos méthodes reste identique...
    def calculer_montant(self):
        """Calcule le montant total de la demande"""
        try:
            from .models import Tarif
            tarif = Tarif.objects.get(type_acte=self.type_acte, actif=True)
            self.tarif_applique = tarif
            self.montant_total = (tarif.prix_unitaire + tarif.timbre_fiscal) * self.nombre_copies
            self.montant_calcule = True
            self.save()
            return self.montant_total
        except Exception:
            raise ValueError(f"Aucun tarif défini pour {getattr(self, 'type_acte', 'cet acte')}")
    
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
    
    # Corriger la méthode confirmer_paiement
    def confirmer_paiement(self):
        """Confirme le paiement et passe au statut suivant"""
        if self.statut != 'EN_ATTENTE_PAIEMENT':
            raise ValueError("La demande doit être en attente de paiement")
        
        if not hasattr(self, 'paiement') or not self.paiement or self.paiement.statut != 'VALIDE':  # Changé de 'CONFIRME' à 'VALIDE'
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
        
        # Envoi de l'email de notification
        try:
            send_mail(
                "Votre acte est prêt",
                f"Votre acte est disponible au téléchargement.",
                "noreply@etatcivil.example.com",
                [self.demandeur.email],
                fail_silently=True,
            )
        except Exception:
            pass
        
        # Générer le document
        try:
            from .models import DocumentNumerique
            doc = DocumentNumerique.objects.create(
                demande=self,
                type_document='ACTE_OFFICIEL',
            )
            doc.generate_acte_pdf()
        except Exception:
            pass
        
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
                hasattr(self, 'paiement') and self.paiement and
                self.paiement.statut == 'VALIDE')
    
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

# Signals
@receiver(pre_save, sender=DemandeActe)
def generate_demande_numbers(sender, instance, **kwargs):
    """Signal pour DemandeActe"""
    if not instance.pk and not instance.numero_demande:
        instance.generate_numero_demande()

        
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
        demande = self.demande
        numero = str(demande.numero_demande).zfill(5)

        if demande.type_acte == 'NAISSANCE':
            acte = demande.personne_concernee.acte_naissance
            pdf_buffer = ActeGenerator.generate_acte_naissance(acte)
            prefix = "Fichactenaiss"
        elif demande.type_acte == 'MARIAGE':
            acte = demande.personne_concernee.mariages_epoux.first() or demande.personne_concernee.mariages_epouse.first()
            pdf_buffer = ActeGenerator.generate_acte_mariage(acte)
            prefix = "Fichactemariage"
        elif demande.type_acte == 'DECES':
            acte = demande.personne_concernee.acte_deces
            pdf_buffer = ActeGenerator.generate_acte_deces(acte)
            prefix = "Fichactedeces"
        else:
            raise ValueError("Type d'acte non supporté")
        
        # Nom du fichier
        filename = f"{prefix}{numero}.pdf"
        self.nom_fichier = filename
        self.type_document = demande.type_acte  # Définir automatiquement le type
        self.fichier.save(filename, ContentFile(pdf_buffer.read()))

        # Signature numérique
        self.sign_document()

        return self.fichier


    # Ajouter une vérification de fichier avant la signature
    def sign_document(self):
        """Signe le document numériquement"""
        if not self.fichier:
            raise ValueError("Aucun fichier à signer")
        
        if not os.path.exists(self.fichier.path):
            raise ValueError("Le fichier n'existe pas sur le système de fichiers")
        
        try:
            file_path = self.fichier.path
            self.signature_numerique = DigitalSigner.sign_document(file_path)
            self.save()
        except Exception as e:
            raise ValueError(f"Erreur lors de la signature : {str(e)}")

    def verify_signature(self):
        """Vérifie la signature numérique du document"""
        if not self.fichier or not self.signature_numerique:
            return False
        
        file_path = self.fichier.path
        return DigitalSigner.verify_signature(file_path, self.signature_numerique)


    def clean(self):
        if not self.signature_numerique and self.fichier:
            self.sign_document()



# Your other model imports and definitions here...

class Paiement(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours'),
        ('VALIDE', 'Validé'),  # Changé de 'CONFIRME' à 'VALIDE' pour cohérence
        ('ECHEC', 'Échec'),
        ('EXPIRE', 'Expiré'),
        ('ANNULE', 'Annulé'),
        ('REMBOURSE', 'Remboursé'),
    ]
    
    MODE_CHOICES = [
        ('CINETPAY', 'CinetPay'),
        ('ESPECES', 'Espèces'),
        ('VIREMENT', 'Virement'),
    ]
    
    demande_acte = models.ForeignKey('DemandeActe', on_delete=models.CASCADE)  # Added quotes in case of circular import
    reference_transaction = models.CharField(max_length=255, unique=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    mode_paiement = models.CharField(max_length=20, choices=MODE_CHOICES, default='CINETPAY')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    
    # Additional fields referenced in the methods
    montant_timbres = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_confirmation = models.DateTimeField(null=True, blank=True)
    date_expiration = models.DateTimeField(null=True, blank=True)
    date_paiement = models.DateTimeField(null=True, blank=True)
    date_remboursement = models.DateTimeField(null=True, blank=True)
    code_erreur = models.CharField(max_length=50, blank=True, default="")
    message_erreur = models.TextField(blank=True, default="")
    commentaire = models.TextField(blank=True, default="")
    methode_paiement = models.CharField(max_length=50, blank=True, default="")
    numero_telephone = models.CharField(max_length=20, blank=True, default="")
    
    # Agent qui a traité
    agent_confirmateur = models.ForeignKey(
        'User',  # Added quotes in case User is defined later or imported differently
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paiements_confirmes',
        help_text="Agent qui a confirmé le paiement"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['reference_transaction']),
        
        ]
        constraints = [
            models.UniqueConstraint(fields=['demande_acte'], name='unique_paiement_par_demande')
        ]
    def clean(self):
        """Validation des données"""
        errors = {}

        # Validation Mobile Money
        if Paiement.objects.filter(demande_acte=self.demande_acte, statut='VALIDE').exists():
            raise ValidationError("Un paiement déjà validé existe pour cette demande.")
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
            montant_calcule = self.montant + self.montant_timbres
            if abs(self.montant_total - montant_calcule) > Decimal('0.01'):
                errors['montant_total'] = (
                    f"Le montant total ({self.montant_total}) ne correspond pas à "
                    f"la somme des montants ({montant_calcule})"
                )

        # Vérification du tarif seulement si self.demande_acte existe et a les attributs nécessaires
        if (self.demande_acte_id and hasattr(self, 'demande_acte') and self.demande_acte and
            hasattr(self.demande_acte, 'type_acte') and hasattr(self.demande_acte, 'tarif_applique') and
            self.demande_acte.tarif_applique):
            try:
                # Import here to avoid circular import
                Tarif = self.__class__._meta.get_field('demande_acte').related_model.tarif_applique.field.related_model
                if not Tarif.objects.filter(pk=self.demande_acte.tarif_applique.pk, actif=True).exists():
                    errors['montant'] = (
                        f"Aucun tarif actif n'est défini pour le type d'acte : {self.demande_acte.tarif_applique}"
                    )
            except Exception:
                pass  # Ignorer les erreurs d'import ou d'accès

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Sauvegarde avec logique métier"""
        # Générer la référence si absente
        if not self.reference_transaction:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            uuid_part = str(uuid.uuid4())[:8].upper()
            self.reference_transaction = f"PAY{timestamp}{uuid_part}"
        
        # Récupération automatique du tarif si montant non défini ET si demande_acte existe
        if (self.demande_acte_id and hasattr(self, 'demande_acte') and self.demande_acte and
            hasattr(self.demande_acte, 'type_acte') and self.demande_acte.type_acte and
            not self.montant):
            try:
                self._calculer_montants_depuis_tarif()
            except Exception:
                pass  # Éviter que l'erreur de calcul empêche la sauvegarde
        
        # Calcul automatique du montant total si pas défini
        if not self.montant_total and self.montant is not None:
            montant_timbres = self.montant_timbres or Decimal('0')
            self.montant_total = self.montant + montant_timbres
        
        # Validation avant sauvegarde
        try:
            self.full_clean()
        except ValidationError as e:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Erreur de validation : {e.messages}")

        super().save(*args, **kwargs)
        
        # Mise à jour du statut de la demande après sauvegarde
        self._mettre_a_jour_demande()
    
    # Dans Paiement, corriger la vérification de tarif
    def _calculer_montants_depuis_tarif(self):
        """Calcule les montants depuis le tarif"""
        if not hasattr(self, 'demande_acte') or not self.demande_acte:
            raise ValueError("Aucune demande associée")
        
        try:
            Tarif = apps.get_model('core', 'Tarif')
            tarif = Tarif.objects.get(
                type_acte=self.demande_acte.type_acte, 
                actif=True
            )
            
            nombre_copies = getattr(self.demande_acte, 'nombre_copies', 1)
            self.montant = tarif.prix_unitaire * nombre_copies
            self.montant_timbres = tarif.timbre_fiscal * nombre_copies
            
        except Tarif.DoesNotExist:
            raise ValidationError(f"Aucun tarif actif trouvé pour {self.demande_acte.type_acte}")
        except Exception as e:
            raise ValidationError(f"Erreur de calcul : {str(e)}")
    
    def _mettre_a_jour_demande(self):
        """Met à jour le statut de la demande selon le paiement"""
        if not self.demande_acte_id or not hasattr(self, 'demande_acte') or not self.demande_acte:
            return
        
        try:
            if (self.statut == 'VALIDE' and  # ← Statut correct
                hasattr(self.demande_acte, 'statut') and 
                self.demande_acte.statut == 'EN_ATTENTE_PAIEMENT'):
                
                if hasattr(self.demande_acte, 'confirmer_paiement'):
                    self.demande_acte.confirmer_paiement()
                else:
                    # Fallback si la méthode n'existe pas
                    self.demande_acte.statut = 'PAIEMENT_CONFIRME'
                    self.demande_acte.save(update_fields=['statut'])
            
            elif (self.statut in ['ECHEC', 'EXPIRE', 'ANNULE'] and 
                  hasattr(self.demande_acte, 'statut') and 
                  self.demande_acte.statut == 'EN_ATTENTE_PAIEMENT'):
                
                # Remettre en attente si le paiement échoue
                self.demande_acte.statut = 'EN_ATTENTE'
                self.demande_acte.save(update_fields=['statut'])
        
        except Exception:
            # Éviter que les erreurs de mise à jour de demande cassent la sauvegarde
            pass
    
    def confirmer(self, agent=None):
        """Confirme le paiement"""
        if self.statut not in ['EN_ATTENTE', 'EN_COURS']:
            raise ValueError(
                f"Impossible de confirmer un paiement avec le statut '{self.statut}'"
            )
        
        self.statut = 'VALIDE'  # Changé de 'CONFIRME' à 'VALIDE'
        self.date_confirmation = timezone.now()
        self.agent_confirmateur = agent
        self.code_erreur = ""
        self.message_erreur = ""
        
        self.save()
        
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
        if self.statut == 'VALIDE':  # ← Statut correct
            raise ValueError(
                "Seuls les paiements validés peuvent être remboursés"
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
        return self.statut == 'VALIDE' 
    
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
        if self.date_confirmation and self.date_paiement:
            return self.date_confirmation - self.date_paiement
        return None
    
    def get_statut_display_with_icon(self):
        """Retourne le statut avec une icône"""
        icons = {
            'EN_ATTENTE': '⏳',
            'VALIDE': '✅',      # ← Corriger
            'ECHEC': '❌',
            'EXPIRE': '⏰',      # ← Ajouter EXPIRE dans STATUT_CHOICES aussi
            'REMBOURSE': '💰',
            'ANNULE': '🚫',
        }
        return f"{icons.get(self.statut)} {self.get_statut_display()}"
    
    def __str__(self):
        return (f"Paiement {self.reference_transaction} - "
                f"{self.montant_total or self.montant} FCFA ({self.get_statut_display()})")
    
    def __repr__(self):
        return (f"<Paiement(id={self.pk}, ref='{self.reference_transaction}', "
                f"montant={self.montant_total or self.montant}, statut='{self.statut}')>")

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



# Signals à la fin du fichier
@receiver(pre_save, sender=ActeNaissance)
@receiver(pre_save, sender=Mariage)
@receiver(pre_save, sender=ActeDeces)
def generate_acte_numbers(sender, instance, **kwargs):
    """Génère les numéros d'acte avant sauvegarde"""
    if not instance.pk and not instance.numero_acte:
        instance.generate_numbers()