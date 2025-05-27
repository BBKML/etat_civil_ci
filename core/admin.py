from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Q
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from django.contrib import messages
from datetime import datetime, timedelta
import calendar
import uuid
from .models import (
    User, Region, Departement, SousPrefecture, Commune, Personne,
    ActeNaissance, Mariage, ActeDeces, DemandeActe, Paiement,
    Tarif, Statistique, LogAudit, DocumentNumerique
)

class RoleBasedQuerysetMixin:
    """Mixin pour filtrer les querysets selon le rôle de l'utilisateur"""
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)
        
        if role == 'ADMINISTRATEUR':
            return qs
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if hasattr(self.model, 'commune_traitement'):
                return qs.filter(commune_traitement=request.user.commune)
            elif hasattr(self.model, 'commune'):
                return qs.filter(commune=request.user.commune)
            elif hasattr(self.model, 'commune_enregistrement'):
                return qs.filter(commune_enregistrement=request.user.commune)
            elif self.model == Personne:
                return qs.filter(
                    Q(commune_naissance=request.user.commune) |
                    Q(commune_residence=request.user.commune)
                )
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if hasattr(self.model, 'commune_traitement'):
                return qs.filter(commune_traitement__sous_prefecture=request.user.commune.sous_prefecture)
            elif hasattr(self.model, 'commune'):
                return qs.filter(commune__sous_prefecture=request.user.commune.sous_prefecture)
            elif self.model == Personne:
                return qs.filter(
                    Q(commune_naissance__sous_prefecture=request.user.commune.sous_prefecture) |
                    Q(commune_residence__sous_prefecture=request.user.commune.sous_prefecture)
                )
        elif role == 'CITOYEN':
            if hasattr(self.model, 'demandeur'):
                return qs.filter(demandeur=request.user)
            elif self.model == Personne:
                # Permet au citoyen de voir les personnes qu'il a créées ou qui le concernent
                return qs.filter(
                    Q(nom=request.user.last_name) |
                    Q(prenoms__icontains=request.user.first_name) |
                    Q(nom_pere=request.user.last_name) |
                    Q(nom_mere=request.user.last_name)
                )
        return qs.none()

    def has_change_permission(self, request, obj=None):
        if getattr(request.user, 'role', None) == 'CITOYEN':
            return obj is None or obj in self.get_queryset(request)
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        if getattr(request.user, 'role', None) == 'CITOYEN' and self.model == Personne:
            return True
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            return False
        elif role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            return False  # Seuls les admins peuvent supprimer
        return super().has_delete_permission(request, obj)

# ========== FILTRES PERSONNALISÉS ==========
class CommuneFilter(admin.SimpleListFilter):
    title = 'Commune'
    parameter_name = 'commune'

    def lookups(self, request, model_admin):
        role = getattr(request.user, 'role', None)
        communes = Commune.objects.none()  # Default empty queryset
        
        if not request.user.is_authenticated:
            return []
            
        if role == 'ADMINISTRATEUR':
            communes = Commune.objects.all()
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if hasattr(request.user, 'commune') and request.user.commune:
                communes = Commune.objects.filter(id=request.user.commune.id)
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if (hasattr(request.user, 'commune') and 
                request.user.commune and 
                hasattr(request.user.commune, 'sous_prefecture')):
                communes = Commune.objects.filter(
                    sous_prefecture=request.user.commune.sous_prefecture
                )
        
        return [(c.id, c.nom) for c in communes]

    def queryset(self, request, queryset):
        if self.value():
            if hasattr(queryset.model, 'commune_traitement'):
                return queryset.filter(commune_traitement_id=self.value())
            elif hasattr(queryset.model, 'commune'):
                return queryset.filter(commune_id=self.value())
            elif queryset.model == Personne:
                return queryset.filter(
                    Q(commune_naissance_id=self.value()) |
                    Q(commune_residence_id=self.value())
                )
        return queryset

class PersonneCommuneFilter(CommuneFilter):
    """Filtre spécifique pour les personnes"""
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                Q(commune_naissance_id=self.value()) |
                Q(commune_residence_id=self.value())
            )
        return queryset

class StatutDemandeFilter(SimpleListFilter):
    title = 'Statut'
    parameter_name = 'statut'

    def lookups(self, request, model_admin):
        return DemandeActe.STATUT_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(statut=self.value())
        return queryset


# ========== ADMIN POUR LES UTILISATEURS ==========
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'commune', 'is_verified')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'numero_cni')
    ordering = ('-date_joined',)



    search_fields = ('username', 'email', 'first_name', 'last_name', 'numero_cni')
    
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        # Filtrer selon le rôle de l'utilisateur actuel
        role = getattr(request.user, 'role', None)
        
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Seulement les citoyens pour ces rôles
            queryset = queryset.filter(role='CITOYEN')
        
        return queryset, use_distinct
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        role = getattr(request.user, 'role', None)

        # Rendre commune obligatoire pour certains rôles
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if 'commune' in form.base_fields:
                form.base_fields['commune'].required = True

        # Cacher les champs sensibles pour les non-admins
        if not request.user.is_superuser and role != 'ADMINISTRATEUR':
            for field in ['role', 'commune', 'is_verified', 'groups', 'user_permissions', 'is_staff']:
                if field in form.base_fields:
                    del form.base_fields[field]

        return form


    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser or request.user.role == 'ADMINISTRATEUR':
            return (
                (None, {'fields': ('username', 'password')}),
                ('Informations personnelles', {
                    'fields': ('email', 'first_name', 'last_name', 'telephone', 'adresse', 'numero_cni', 'photo')
                }),
                ('Permissions spéciales', {
                    'fields': ('role', 'commune', 'is_verified', 'is_active', 'is_staff', 'groups', 'user_permissions'),
                    'classes': ('collapse',)
                }),
                ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
            )
        else:
            return (
                (None, {'fields': ('username', 'password')}),
                ('Informations personnelles', {
                    'fields': ('email', 'first_name', 'last_name', 'telephone', 'adresse', 'numero_cni', 'photo')
                }),
                # Ne pas inclure le fieldset "Permissions spéciales"
            )



    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and not request.user.is_superuser and request.user.role != 'ADMINISTRATEUR':
            readonly_fields += ('role', 'commune', 'is_verified')
        return readonly_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'ADMINISTRATEUR':
            return qs
        elif role == 'MAIRE':
            return qs.filter(Q(commune=request.user.commune) | Q(role='CITOYEN'))
        elif role == 'SOUS_PREFET':
            return qs.filter(
                Q(commune__sous_prefecture=request.user.commune.sous_prefecture) |
                Q(role='CITOYEN')
            )
        elif role in ['AGENT_COMMUNE', 'AGENT_SOUS_PREFECTURE']:
            # Laisser voir leur propre profil uniquement
            return qs.filter(id=request.user.id)
        elif role == 'CITOYEN':
            return qs.filter(id=request.user.id)
        else:
            # Cas par défaut - éviter de renvoyer rien
            return qs.none()


    def save_model(self, request, obj, form, change):
        role = getattr(obj, 'role', None)
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if not obj.commune:
                messages.error(request, 'Une commune doit être spécifiée pour ce rôle')
                return
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.role == 'ADMINISTRATEUR':
            return True
        # Par exemple, agents peuvent voir uniquement leur propre profil
        if request.user.role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None or obj == request.user:
                return True
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.role == 'ADMINISTRATEUR':
            return True
        if obj is not None:
            if obj == request.user:
                # Tous les utilisateurs peuvent modifier leur propre profil
                return True
        return False


    def has_delete_permission(self, request, obj=None):
        # Seuls les superusers et admins peuvent supprimer
        return request.user.is_superuser or request.user.role == 'ADMINISTRATEUR'

    def has_module_permission(self, request):
        return request.user.is_staff and (
            request.user.is_superuser or
            request.user.role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']
        )

# ========== ADMIN POUR LES STRUCTURES TERRITORIALES ==========
# Ces classes ne sont accessibles qu'aux administrateurs
class AdminOnlyMixin:
    def has_module_permission(self, request):
        return getattr(request.user, 'role', None) == 'ADMINISTRATEUR'

@admin.register(Region)
class RegionAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = ('nom', 'code_region', 'nombre_departements')
    search_fields = ('nom', 'code_region')
    
    def nombre_departements(self, obj):
        return obj.departements.count()
    nombre_departements.short_description = 'Nb Départements'

@admin.register(Departement)
class DepartementAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = ('nom', 'code_departement', 'region', 'nombre_sous_prefectures')
    list_filter = ('region',)
    search_fields = ('nom', 'code_departement')
    
    def nombre_sous_prefectures(self, obj):
        return obj.sous_prefectures.count()
    nombre_sous_prefectures.short_description = 'Nb Sous-Préfectures'

@admin.register(SousPrefecture)
class SousPrefectureAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = ('nom', 'code_sous_prefecture', 'departement', 'telephone', 'nombre_communes')
    list_filter = ('departement__region', 'departement')
    search_fields = ('nom', 'code_sous_prefecture')
    
    def nombre_communes(self, obj):
        return obj.communes.count()
    nombre_communes.short_description = 'Nb Communes'

@admin.register(Commune)
class CommuneAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = ('nom', 'code_commune', 'sous_prefecture', 'telephone', 'email', 'statistiques_mois')
    list_filter = ('sous_prefecture__departement__region', 'sous_prefecture__departement', 'sous_prefecture')
    search_fields = ('nom', 'code_commune')
    
    def statistiques_mois(self, obj):
        current_month = timezone.now().month
        current_year = timezone.now().year
        stats = obj.statistiques.filter(annee=current_year, mois=current_month).first()
        if stats:
            return f"N:{stats.naissances_total} M:{stats.mariages_total} D:{stats.deces_total}"
        return "Aucune données"
    statistiques_mois.short_description = 'Stats du mois'

# ========== ADMIN POUR LES PERSONNES ==========
# ========== ADMIN POUR LES PERSONNES ==========
@admin.register(Personne)
class PersonneAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'date_naissance', 'sexe', 'commune_naissance', 'situation_matrimoniale')
    list_filter = ('sexe', 'situation_matrimoniale', PersonneCommuneFilter)
    search_fields = ('nom', 'prenoms', 'nom_pere', 'nom_mere', 'numero_unique')
    date_hierarchy = 'date_naissance'
    exclude = ('user',)


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'CITOYEN':
            # Le citoyen ne peut voir que sa propre fiche
            return qs.filter(user=request.user)
        
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            # L'agent de commune ne peut voir que les personnes de sa commune
            return qs.filter(commune_residence=request.user.commune)

        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Le sous-préfet voit les personnes de toutes les communes de sa sous-préfecture
            return qs.filter(commune_residence__sous_prefecture=request.user.commune.sous_prefecture)

        # Les administrateurs voient tout
        return qs


    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            # Limiter les champs modifiables pour les citoyens
            if 'formfield_for_foreignkey' not in kwargs:
                kwargs['formfield_for_foreignkey'] = self.formfield_for_foreignkey
            
            # Rendre certains champs obligatoires
            for field in ['nom', 'prenoms', 'date_naissance', 'lieu_naissance', 'sexe']:
                if field in form.base_fields:
                    form.base_fields[field].required = True
        
        return form
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        role = getattr(request.user, 'role', None)
        
        if db_field.name in ['commune_naissance', 'commune_residence']:
            if role == 'ADMINISTRATEUR':
                pass  # Toutes les communes disponibles
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = Commune.objects.filter(id=request.user.commune.id)
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = Commune.objects.filter(
                    sous_prefecture=request.user.commune.sous_prefecture
                )
            elif role == 'CITOYEN':
                # Le citoyen peut sélectionner n'importe quelle commune
                pass
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        role = getattr(request.user, 'role', None)

        if not change:
            if role == 'CITOYEN':
                if (obj.nom != request.user.last_name or obj.prenoms != request.user.first_name):
                    messages.warning(
                        request, 
                        "Les informations ne correspondent pas à votre profil. "
                        "Veuillez vérifier les noms et prénoms."
                    )
            obj.user = request.user  # l'utilisateur connecté est lié
        
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE', 'CITOYEN']
    
    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN' and obj is not None:
            return obj.user == request.user  # seulement sa propre fiche
        if role == 'AGENT_COMMUNE' and obj is not None:
            return obj.commune_residence == request.user.commune
        return super().has_change_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    # ========== ADMIN POUR LES ACTES ==========
@admin.register(ActeNaissance)
class ActeNaissanceAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('numero_acte', 'get_nom_complet', 'date_enregistrement', 'commune_enregistrement', 'agent_enregistreur')
    list_filter = ('commune_enregistrement', 'date_enregistrement')
    search_fields = ('numero_acte', 'personne__nom', 'personne__prenoms')
    date_hierarchy = 'date_enregistrement'
    autocomplete_fields = ['personne', 'agent_enregistreur']  # Remplacer raw_id_fields
    
    def get_nom_complet(self, obj):
        return f"{obj.personne.nom} {obj.personne.prenoms}"
    get_nom_complet.short_description = 'Nom complet'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtre pour le champ personne
        if db_field.name == "personne":
            role = getattr(request.user, 'role', None)
            
            if role == 'ADMINISTRATEUR':
                pass  # Toutes les personnes disponibles
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance=request.user.commune
                )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance__sous_prefecture=request.user.commune.sous_prefecture
                )
        
        # Filtre pour le champ agent_enregistreur
        elif db_field.name == "agent_enregistreur":
            role = getattr(request.user, 'role', None)
            
            if role == 'ADMINISTRATEUR':
                kwargs["queryset"] = User.objects.filter(
                    role__in=['AGENT_COMMUNE', 'MAIRE', 'ADMINISTRATEUR']
                )
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = User.objects.filter(
                    Q(commune=request.user.commune) &
                    Q(role__in=['AGENT_COMMUNE', 'MAIRE'])
                )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = User.objects.filter(
                    Q(commune__sous_prefecture=request.user.commune.sous_prefecture) &
                    Q(role__in=['AGENT_COMMUNE', 'MAIRE'])
                )
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['agent_enregistreur'] = request.user
        return initial
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']
    def get_nom_complet(self, obj):
        return f"{obj.personne.nom} {obj.personne.prenoms}"
    get_nom_complet.short_description = 'Nom complet'
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

@admin.register(Mariage)
class MariageAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('numero_acte', 'get_epoux', 'get_epouse', 'date_mariage', 'commune_mariage', 'regime_matrimonial')
    list_filter = ('commune_mariage', 'date_mariage', 'regime_matrimonial')
    search_fields = ('numero_acte', 'epoux__nom', 'epouse__nom')
    date_hierarchy = 'date_mariage'
    autocomplete_fields = ['epoux', 'epouse', 'commune_mariage', 'officier_etat_civil']
    def get_epoux(self, obj):
        return f"{obj.epoux.nom} {obj.epoux.prenoms}"
    get_epoux.short_description = 'Époux'
    
    def get_epouse(self, obj):
        return f"{obj.epouse.nom} {obj.epouse.prenoms}"
    get_epouse.short_description = 'Épouse'
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

@admin.register(ActeDeces)
class ActeDecesAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('numero_acte', 'get_nom_complet', 'date_deces', 'commune_deces', 'agent_enregistreur')
    list_filter = ('commune_deces', 'date_deces')
    search_fields = ('numero_acte', 'personne__nom', 'personne__prenoms')
    date_hierarchy = 'date_deces'
    autocomplete_fields = ['personne', 'agent_enregistreur']  # Seuls les champs qui existent dans ActeDeces
    
    def get_nom_complet(self, obj):
        return f"{obj.personne.nom} {obj.personne.prenoms}"
    get_nom_complet.short_description = 'Nom complet'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filtre pour le champ personne
        if db_field.name == "personne":
            role = getattr(request.user, 'role', None)
            
            if role == 'ADMINISTRATEUR':
                pass  # Toutes les personnes disponibles
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance=request.user.commune
                )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance__sous_prefecture=request.user.commune.sous_prefecture
                )
        
        # Filtre pour le champ agent_enregistreur
        elif db_field.name == "agent_enregistreur":
            role = getattr(request.user, 'role', None)
            
            if role == 'ADMINISTRATEUR':
                kwargs["queryset"] = User.objects.filter(
                    role__in=['AGENT_COMMUNE', 'MAIRE', 'ADMINISTRATEUR']
                )
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = User.objects.filter(
                    Q(commune=request.user.commune) &
                    Q(role__in=['AGENT_COMMUNE', 'MAIRE'])
                )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = User.objects.filter(
                    Q(commune__sous_prefecture=request.user.commune.sous_prefecture) &
                    Q(role__in=['AGENT_COMMUNE', 'MAIRE'])
                )
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['agent_enregistreur'] = request.user
        return initial
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']
    

# ========== ADMIN POUR LES DEMANDES D'ACTES ==========
@admin.register(DemandeActe)
class DemandeActeAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'numero_demande', 'type_acte', 'get_personne_concernee',
        'demandeur', 'statut', 'date_demande', 'action_buttons'
    )
    list_filter = (CommuneFilter, StatutDemandeFilter, 'type_acte')
    search_fields = (
        'numero_demande', 'personne_concernee__nom',
        'personne_concernee__prenoms', 'demandeur__username'
    )
    date_hierarchy = 'date_demande'
    readonly_fields = ('numero_demande', 'date_demande')
    autocomplete_fields = ['demandeur', 'personne_concernee', 'agent_traitant']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'CITOYEN':
            return qs.filter(demandeur=request.user)  # Voir uniquement ses propres demandes
        return qs

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            # Les citoyens ne peuvent pas modifier une demande après soumission
            return False
        return super().has_change_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            if obj is None:
                return True
            return obj.demandeur == request.user  # Voir uniquement leurs demandes
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        # Tous les rôles peuvent créer une demande
        return True

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            return False  # Les citoyens ne peuvent pas supprimer leurs demandes
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if getattr(request.user, 'role', None) == 'CITOYEN':
            readonly_fields += ('demandeur',)
        return readonly_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        role = getattr(request.user, 'role', None)

        if db_field.name == "personne_concernee":
            if role == 'ADMINISTRATEUR':
                pass
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance=request.user.commune
                )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = Personne.objects.filter(
                    commune_naissance__sous_prefecture=request.user.commune.sous_prefecture
                )
            elif role == 'CITOYEN':
                kwargs["queryset"] = Personne.objects.filter(
                    Q(nom=request.user.last_name) |
                    Q(prenoms__icontains=request.user.first_name)
                )

        elif db_field.name == "demandeur":
            if role == 'ADMINISTRATEUR':
                kwargs["queryset"] = User.objects.all()
            elif role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                kwargs["queryset"] = User.objects.filter(role='CITOYEN')
            elif role == 'CITOYEN':
                kwargs["queryset"] = User.objects.filter(id=request.user.id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['demandeur'] = request.user
        return initial

    def get_personne_concernee(self, obj):
        return f"{obj.personne_concernee.nom} {obj.personne_concernee.prenoms}"
    get_personne_concernee.short_description = 'Personne concernée'

    def action_buttons(self, obj):
        from django.urls import reverse
        from django.utils.safestring import mark_safe

        role = getattr(self, 'request', None)
        role = getattr(role.user, 'role', None) if role else None

        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE'] and obj.statut == 'EN_ATTENTE':
            url = reverse('admin:core_demandeacte_change', args=[obj.pk])
            return mark_safe(f'<a href="{url}" class="button">Traiter</a>')
        elif role == 'CITOYEN' and obj.statut == 'DELIVRE':
            return mark_safe('<a href="#" class="button">Télécharger PDF</a>')
        return ""
    action_buttons.short_description = 'Actions'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if getattr(request.user, 'role', None) == 'CITOYEN':
            return {}  # Pas d'actions pour les citoyens
        return actions

    def approuver_demandes(self, request, queryset):
        updated = queryset.filter(statut='EN_ATTENTE').update(statut='APPROUVE')
        self.message_user(request, f"{updated} demande(s) approuvée(s).")
    approuver_demandes.short_description = "Approuver les demandes sélectionnées"

    def rejeter_demandes(self, request, queryset):
        updated = queryset.filter(statut='EN_ATTENTE').update(statut='REJETE')
        self.message_user(request, f"{updated} demande(s) rejetée(s).")
    rejeter_demandes.short_description = "Rejeter les demandes sélectionnées"

    def marquer_delivrees(self, request, queryset):
        updated = queryset.filter(statut='APPROUVE').update(statut='DELIVRE')
        self.message_user(request, f"{updated} demande(s) marquée(s) comme délivrée(s).")
    marquer_delivrees.short_description = "Marquer comme délivrées"

    def has_module_permission(self, request):
        return hasattr(request.user, 'role')  # Tous les rôles peuvent accéder au module

# ========== ADMIN POUR LES PAIEMENTS ==========
@admin.register(Paiement)
class PaiementAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'reference_transaction', 'get_demande', 'montant',
        'methode_paiement', 'statut', 'date_paiement'
    )
    list_filter = ('statut', 'methode_paiement', 'date_paiement')
    search_fields = ('reference_transaction', 'demande__numero_demande')
    readonly_fields = ('reference_transaction', 'date_paiement')

    def get_demande(self, obj):
        return obj.demande.numero_demande
    get_demande.short_description = 'N° Demande'


    # Autoriser le citoyen à ne voir que ses propres paiements
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, 'role', None) == 'CITOYEN':
            return qs.filter(demande__demandeur=request.user)
        return qs

    # Pour préremplir le champ "demande" et s'assurer que le citoyen ne paye que ses propres demandes
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'demande':
            role = getattr(request.user, 'role', None)
            if role == 'CITOYEN':
                kwargs['queryset'] = DemandeActe.objects.filter(demandeur=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if getattr(request.user, 'role', None) == 'CITOYEN':
            readonly_fields += ('statut',)  # Le citoyen ne peut pas modifier le statut du paiement
        return readonly_fields

    def has_module_permission(self, request):
        # Tous les rôles peuvent accéder au module
        return hasattr(request.user, 'role')

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN' and obj is not None:
            return obj.demande.demandeur == request.user
        return True

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            return False  # Le citoyen ne peut pas supprimer les paiements
        return True
    def has_add_permission(self, request):
            role = getattr(request.user, 'role', None)
            return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE', 'CITOYEN']
        
    # ========== ADMIN POUR LES TARIFS ==========
@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = ('type_acte', 'prix_unitaire', 'timbre_fiscal', 'get_prix_total', 'actif', 'date_application')
    list_filter = ('actif', 'date_application')
    
    def get_prix_total(self, obj):
        return obj.prix_unitaire + obj.timbre_fiscal
    get_prix_total.short_description = 'Prix Total'
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

# ========== ADMIN POUR LES STATISTIQUES ==========
@admin.register(Statistique)
class StatistiqueAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('commune', 'mois', 'annee', 'naissances_total', 'mariages_total', 'deces_total', 'revenus_total')
    list_filter = ('annee', 'mois', 'commune')
    readonly_fields = ('date_creation',)
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

# ========== ADMIN POUR LES LOGS D'AUDIT ==========
@admin.register(LogAudit)
class LogAuditAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'action', 'table_concernee', 'description', 'adresse_ip', 'date_action')
    list_filter = ('action', 'table_concernee', 'date_action')
    search_fields = ('utilisateur__username', 'description', 'adresse_ip')
    readonly_fields = ('utilisateur', 'action', 'table_concernee', 'objet_id', 'description', 'adresse_ip', 'date_action')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return getattr(request.user, 'role', None) == 'ADMINISTRATEUR'
    
    def has_module_permission(self, request):
        return getattr(request.user, 'role', None) == 'ADMINISTRATEUR'

# ========== ADMIN POUR LES DOCUMENTS NUMÉRIQUES ==========
@admin.register(DocumentNumerique)
class DocumentNumeriqueAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = ('nom_fichier', 'type_document', 'get_demande', 'date_creation')
    list_filter = ('type_document', 'date_creation')
    search_fields = ('nom_fichier', 'demande__numero_demande')
    readonly_fields = ('date_creation', 'signature_numerique')
    
    def get_demande(self, obj):
        return obj.demande.numero_demande
    get_demande.short_description = 'N° Demande'
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

# ========== CONFIGURATION DU SITE ADMIN ==========
admin.site.site_header = "Système de Gestion Intégré de l'État Civil"
admin.site.site_title = "État Civil CI"
admin.site.index_title = "Administration de l'État Civil"

# ========== FONCTIONS POUR LES TABLEAUX DE BORD ==========
def get_dashboard_data(user):
    """Retourne les données du tableau de bord selon le rôle de l'utilisateur"""
    data = {}
    role = getattr(user, 'role', None)
    
    if role == 'ADMINISTRATEUR':
        # Données globales pour l'administrateur
        data.update({
            'total_communes': Commune.objects.count(),
            'total_demandes_mois': DemandeActe.objects.filter(
                date_demande__month=timezone.now().month,
                date_demande__year=timezone.now().year
            ).count(),
            'demandes_en_attente': DemandeActe.objects.filter(statut='EN_ATTENTE').count(),
            'revenus_mois': Paiement.objects.filter(
                statut='CONFIRME',
                date_paiement__month=timezone.now().month,
                date_paiement__year=timezone.now().year
            ).aggregate(total=Sum('montant'))['total'] or 0,
            'total_utilisateurs': User.objects.count(),
            'total_actes_mois': (
                ActeNaissance.objects.filter(
                    date_enregistrement__month=timezone.now().month,
                    date_enregistrement__year=timezone.now().year
                ).count() +
                Mariage.objects.filter(
                    date_mariage__month=timezone.now().month,
                    date_mariage__year=timezone.now().year
                ).count() +
                ActeDeces.objects.filter(
                    date_deces__month=timezone.now().month,
                    date_deces__year=timezone.now().year
                ).count()
            ),
        })
    
    elif role in ['AGENT_COMMUNE', 'MAIRE']:
        # Données pour les agents communaux et maires
        commune = user.commune
        if commune:
            data.update({
                'demandes_aujourd_hui': DemandeActe.objects.filter(
                    commune_traitement=commune,
                    date_demande__date=timezone.now().date()
                ).count(),
                'demandes_en_attente': DemandeActe.objects.filter(
                    commune_traitement=commune,
                    statut='EN_ATTENTE'
                ).count(),
                'demandes_traitees_mois': DemandeActe.objects.filter(
                    commune_traitement=commune,
                    statut__in=['APPROUVE', 'DELIVRE'],
                    date_traitement__month=timezone.now().month
                ).count(),
                'revenus_mois': Paiement.objects.filter(
                    demande__commune_traitement=commune,
                    statut='CONFIRME',
                    date_paiement__month=timezone.now().month
                ).aggregate(total=Sum('montant'))['total'] or 0,
                'actes_enregistres_mois': (
                    ActeNaissance.objects.filter(
                        commune_enregistrement=commune,
                        date_enregistrement__month=timezone.now().month
                    ).count() +
                    Mariage.objects.filter(
                        commune_mariage=commune,
                        date_mariage__month=timezone.now().month
                    ).count() +
                    ActeDeces.objects.filter(
                        commune_deces=commune,
                        date_deces__month=timezone.now().month
                    ).count()
                ),
            })
    
    elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
        # Données pour les sous-préfets et agents de sous-préfecture
        sous_prefecture = user.commune.sous_prefecture if user.commune else None
        if sous_prefecture:
            data.update({
                'demandes_aujourd_hui': DemandeActe.objects.filter(
                    commune_traitement__sous_prefecture=sous_prefecture,
                    date_demande__date=timezone.now().date()
                ).count(),
                'demandes_en_attente': DemandeActe.objects.filter(
                    commune_traitement__sous_prefecture=sous_prefecture,
                    statut='EN_ATTENTE'
                ).count(),
                'demandes_traitees_mois': DemandeActe.objects.filter(
                    commune_traitement__sous_prefecture=sous_prefecture,
                    statut__in=['APPROUVE', 'DELIVRE'],
                    date_traitement__month=timezone.now().month
                ).count(),
                'revenus_mois': Paiement.objects.filter(
                    demande__commune_traitement__sous_prefecture=sous_prefecture,
                    statut='CONFIRME',
                    date_paiement__month=timezone.now().month
                ).aggregate(total=Sum('montant'))['total'] or 0,
                'communes_geres': Commune.objects.filter(sous_prefecture=sous_prefecture).count(),
            })
    
        elif role == 'CITOYEN':
        # Données pour les citoyens - plus détaillées
            demandes = DemandeActe.objects.filter(demandeur=user)
            personnes = Personne.objects.filter(
                Q(nom=user.last_name) |
                Q(prenoms__icontains=user.first_name) |
                Q(nom_pere=user.last_name) |
                Q(nom_mere=user.last_name)
            )
            paiements = Paiement.objects.filter(demande__demandeur=user)
            
            data.update({
                'mes_demandes_count': demandes.count(),
                'mes_personnes_count': personnes.count(),
                'mes_paiements_count': paiements.count(),
                'demandes_en_cours': demandes.filter(statut__in=['EN_ATTENTE', 'EN_COURS']).count(),
                'demandes_delivrees': demandes.filter(statut='DELIVRE').count(),
                'demandes_rejetes': demandes.filter(statut='REJETE').count(),
                'paiements_en_attente': paiements.filter(statut='EN_ATTENTE').count(),
                'paiements_confirmees': paiements.filter(statut='CONFIRME').count(),
                'recentes_demandes': list(demandes.order_by('-date_demande')[:5].values(
                    'numero_demande', 'type_acte', 'statut', 'date_demande'
                )),
                'recentes_personnes': list(personnes.order_by('-date_creation')[:5].values(
                    'nom', 'prenoms', 'date_naissance', 'commune_naissance__nom'
                )),
                'recentes_paiements': list(paiements.order_by('-date_paiement')[:5].values(
                    'reference_transaction', 'montant', 'statut', 'date_paiement'
                )),
            })
    
    return data

# ========== VUES PERSONNALISÉES ==========
from django.shortcuts import render
from django.http import JsonResponse

def custom_admin_index(request):
    """Vue personnalisée pour l'index admin avec tableau de bord selon le rôle"""
    context = {
        **admin.site.each_context(request),
        'dashboard_data': get_dashboard_data(request.user),
        'user_role': getattr(request.user, 'role', None),
    }
    
    role = getattr(request.user, 'role', None)
    
    # Données supplémentaires pour les agents et administrateurs
    if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE', 'ADMINISTRATEUR']:
        # Récupérer les 5 dernières demandes selon le rôle
        if role in ['AGENT_COMMUNE', 'MAIRE']:
            recent_demandes = DemandeActe.objects.filter(
                commune_traitement=request.user.commune
            ).order_by('-date_demande')[:5]
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            recent_demandes = DemandeActe.objects.filter(
                commune_traitement__sous_prefecture=request.user.commune.sous_prefecture
            ).order_by('-date_demande')[:5]
        else:  # ADMINISTRATEUR
            recent_demandes = DemandeActe.objects.all().order_by('-date_demande')[:5]
        
        # Récupérer les 5 dernières activités
        recent_logs = LogAudit.objects.filter(
            utilisateur=request.user
        ).order_by('-date_action')[:5]
        
        context.update({
            'recent_demandes': recent_demandes,
            'recent_logs': recent_logs,
        })
    
    # Template selon le rôle
    if role == 'ADMINISTRATEUR':
        template = 'admin/index_admin.html'
    elif role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
        template = 'admin/index_agent.html'
    elif role == 'CITOYEN':
        # Récupérer les objets complets pour les modèles clés
        context['mes_demandes'] = DemandeActe.objects.filter(demandeur=request.user).order_by('-date_demande')[:5]
        context['mes_personnes'] = Personne.objects.filter(
            Q(nom=request.user.last_name) |
            Q(prenoms__icontains=request.user.first_name) |
            Q(nom_pere=request.user.last_name) |
            Q(nom_mere=request.user.last_name)
        ).order_by('-date_creation')[:5]
        context['mes_paiements'] = Paiement.objects.filter(
            demande__demandeur=request.user
        ).order_by('-date_paiement')[:5]
        
        template = 'admin/index_citoyen.html'
    else:
        template = 'admin/index.html'
    
    return render(request, template, context)

def dashboard_data_view(request):
    """Endpoint pour les données AJAX du tableau de bord"""
    data = get_dashboard_data(request.user)
    return JsonResponse(data)



# core/admin.py
from django.contrib.admin import AdminSite
from django.urls import path
from django.views.generic import TemplateView

class CustomAdminSite(AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('help-guide/', self.admin_view(TemplateView.as_view(template_name='admin/help_guide.html'))), 
            path('tarifs/', self.admin_view(TemplateView.as_view(template_name='admin/tarifs.html'))),
            path('contact/', self.admin_view(TemplateView.as_view(template_name='admin/contact.html'))),
        ]
        return custom_urls + urls

custom_admin_site = CustomAdminSite(name='custom_admin')