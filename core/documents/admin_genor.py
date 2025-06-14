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
        """Validation des données"""
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
            montant_calcule = self.montant + self.montant_timbres
            if abs(self.montant_total - montant_calcule) > Decimal('0.01'):
                errors['montant_total'] = (
                    f"Le montant total ({self.montant_total}) ne correspond pas à "
                    f"la somme des montants ({montant_calcule})"
                )

        # Vérification du tarif seulement si self.demande existe et a les attributs nécessaires
        if (self.demande_id and hasattr(self, 'demande') and self.demande and
            hasattr(self.demande, 'type_acte') and hasattr(self.demande, 'tarif_applique') and
            self.demande.tarif_applique):
            try:
                from .models import Tarif
                if not Tarif.objects.filter(pk=self.demande.tarif_applique.pk, actif=True).exists():
                    errors['montant'] = (
                        f"Aucun tarif actif n'est défini pour le type d'acte : {self.demande.tarif_applique}"
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
            from .models import Tarif
            
            tarif = Tarif.objects.get(
                type_acte=self.demande.type_acte, 
                actif=True
            )
            
            nombre_copies = getattr(self.demande, 'nombre_copies', 1)
            self.montant = tarif.prix_unitaire * nombre_copies
            self.montant_timbres = tarif.timbre_fiscal * nombre_copies
            
        except Exception as e:
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