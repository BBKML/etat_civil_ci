import calendar
import json
import uuid
from datetime import datetime, timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count, Q, Sum
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from .acte_generator import ActeGenerator
from .digital_signer import DigitalSigner

from .models import (
    User, Region, Departement, SousPrefecture, Commune, Personne,
    ActeNaissance, Mariage, ActeDeces, DemandeActe, Paiement,
    Tarif, Statistique, LogAudit, DocumentNumerique
)
from .services.payment_service import CinetPayService



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
                return qs.filter(user=request.user)

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
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Q
from django.utils.html import format_html
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'commune', 'photo_thumbnail')
    list_filter = ('is_verified', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'numero_cni')
    ordering = ('-date_joined',)
    list_per_page = 10
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'email', 'photo', 'photo_preview')
        }),
        ('Informations supplémentaires', {
            'fields': ('commune', 'is_verified', 'numero_cni')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Dates importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('photo_preview',)

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.update_verbose_names()

    def update_verbose_names(self):
        """Met à jour les noms affichés selon le contexte (placeholder)."""
        pass

    # Personnalisation du titre selon rôle utilisateur dans la vue liste
    def changelist_view(self, request, extra_context=None):
        if getattr(request.user, 'role', None) == 'CITOYEN':
            original_verbose_name = self.model._meta.verbose_name
            original_verbose_name_plural = self.model._meta.verbose_name_plural
            self.model._meta.verbose_name = "Profil"
            self.model._meta.verbose_name_plural = "Mon Profil"
            try:
                return super().changelist_view(request, extra_context)
            finally:
                self.model._meta.verbose_name = original_verbose_name
                self.model._meta.verbose_name_plural = original_verbose_name_plural
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            original_verbose_name = self.model._meta.verbose_name
            self.model._meta.verbose_name = "Profil"
            try:
                return super().change_view(request, object_id, form_url, extra_context)
            finally:
                self.model._meta.verbose_name = original_verbose_name
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            original_verbose_name = self.model._meta.verbose_name
            self.model._meta.verbose_name = "Profil"
            try:
                return super().add_view(request, form_url, extra_context)
            finally:
                self.model._meta.verbose_name = original_verbose_name
        return super().add_view(request, form_url, extra_context)

    # Affichage miniature dans la liste
    def photo_thumbnail(self, obj):
        if obj.photo and hasattr(obj.photo, 'url'):
            try:
                return format_html(
                    '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                    obj.photo.url
                )
            except (ValueError, AttributeError):
                return "Photo non disponible"
        return "Aucune photo"
    photo_thumbnail.short_description = 'Photo'

    # Aperçu photo dans formulaire
    def photo_preview(self, obj):
        if obj and obj.pk and obj.photo and hasattr(obj.photo, 'url'):
            try:
                return format_html(
                    '''
                    <div style="margin: 10px 0;">
                        <img src="{}" width="150" height="150" 
                             style="border-radius: 10px; object-fit: cover; border: 2px solid #ddd;" />
                        <p style="margin-top: 5px; font-size: 12px; color: #666;">
                            Aperçu actuel de la photo
                        </p>
                    </div>
                    ''',
                    obj.photo.url
                )
            except (ValueError, AttributeError):
                return format_html('<p style="color: red;">Photo non disponible</p>')
        return format_html('<p style="color: #999;">Aucune photo uploadée</p>')

    photo_preview.short_description = 'Aperçu de la photo actuelle'

    # Recherche personnalisée selon rôle
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        role = getattr(request.user, 'role', None)
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Les agents peuvent chercher parmi tous les utilisateurs de leur structure
            pass  # Le filtrage se fait déjà dans get_queryset
        return queryset, use_distinct

    # Formulaire personnalisé selon rôle
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        role = getattr(request.user, 'role', None)

        # Pour les agents, s'assurer que la commune est requise
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if 'commune' in form.base_fields:
                form.base_fields['commune'].required = True

        # Retirer les champs sensibles pour les non-administrateurs
        if not request.user.is_superuser and role != 'ADMINISTRATEUR':
            sensitive_fields = ['role', 'is_verified', 'groups', 'user_permissions', 'is_staff', 'is_superuser']
            for field in sensitive_fields:
                form.base_fields.pop(field, None)

        return form

    # Champs en lecture seule selon rôle
    def get_readonly_fields(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        readonly_fields = list(self.readonly_fields)  # Inclut 'photo_preview'
        
        # Si c'est un superuser ou administrateur, pas de restrictions supplémentaires
        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return readonly_fields
        
        # Pour les agents qui consultent des profils d'autres utilisateurs
        if obj and obj.pk != request.user.pk:
            if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                # Les agents peuvent voir mais pas modifier les profils des autres
                return [field.name for field in self.model._meta.fields] + ['photo_preview']
        
        # Pour les citoyens et agents modifiant leur propre profil
        # Ils ne peuvent pas modifier ces champs système
        readonly_fields.extend(['last_login', 'date_joined', 'is_active', 'is_staff', 'is_superuser'])
        
        return readonly_fields

    # Jeux de champs selon rôle (pour formulaire)
    def get_fieldsets(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        
        # Pour superuser et administrateur - accès complet
        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return (
                (None, {'fields': ('username', 'password')}),
                ('Informations personnelles', {
                    'fields': ('email', 'first_name', 'last_name', 'telephone', 'adresse', 'numero_cni', 'photo', 'photo_preview', 'commune')
                }),
                ('Permissions spéciales', {
                    'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'groups', 'user_permissions'),
                    'classes': ('collapse',)
                }),
                ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
            )
        
        # Pour citoyens et agents - champs modifiables
        return (
            (None, {'fields': ('username',)}),
            ('Informations personnelles', {
                'fields': ('first_name', 'last_name', 'email', 'telephone', 'photo', 'photo_preview', 'commune')
            }),
            ('Informations système', {
                'fields': ('last_login', 'date_joined'),
                'classes': ('collapse',)
            }),
        )

    # Permissions : modification
    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if obj and obj.role == 'CITOYEN' and request.user.role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
           return False

        # Superuser et administrateur peuvent tout modifier
        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        
        # Si pas d'objet spécifique, autoriser l'accès général
        if obj is None:
            return True
        
        # Un utilisateur peut toujours modifier son propre profil
        if obj.pk == request.user.pk:
            return True
        
        # Les agents ne peuvent pas modifier les profils des autres (seulement consulter)
        return False

    # Permissions : suppression
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, 'role', None) == 'ADMINISTRATEUR'

    # Permission : vue
    def has_view_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        
        # Superuser et administrateur voient tout
        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        
        # Si pas d'objet spécifique ou c'est son propre profil
        if obj is None or obj.pk == request.user.pk:
            return True

        # Permissions pour les agents selon leur structure
        if role == 'MAIRE':
            return (obj.commune == request.user.commune) or (obj.role == 'CITOYEN')
        elif role == 'SOUS_PREFET':
            return (obj.commune and obj.commune.sous_prefecture == request.user.commune.sous_prefecture) or (obj.role == 'CITOYEN')
        elif role in ['AGENT_COMMUNE', 'AGENT_SOUS_PREFECTURE']:
            # Les agents peuvent voir les utilisateurs de leur structure
            if role == 'AGENT_COMMUNE':
                return obj.commune == request.user.commune
            else:  # AGENT_SOUS_PREFECTURE
                return obj.commune and obj.commune.sous_prefecture == request.user.commune.sous_prefecture
        
        return False

    # Permission : accès au module admin
    def has_module_permission(self, request):
        return (
            request.user.is_authenticated and
            request.user.is_staff and
            (request.user.is_superuser or
             getattr(request.user, 'role', None) in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE', 'CITOYEN'])
        )

    # CORRECTION 1: Queryset filtré selon rôle - permettre aux citoyens de voir leur profil
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return qs
        elif role == 'MAIRE':
            # Le maire voit tous les utilisateurs de sa commune + les citoyens
            return qs.filter(Q(commune=request.user.commune) | Q(role='CITOYEN'))
        elif role == 'SOUS_PREFET':
            # Le sous-préfet voit tous les utilisateurs de sa sous-préfecture + les citoyens
            return qs.filter(
                Q(commune__sous_prefecture=request.user.commune.sous_prefecture) |
                Q(role='CITOYEN')
            )
        elif role == 'AGENT_COMMUNE':
            # L'agent communal voit tous les utilisateurs de sa commune
            return qs.filter(commune=request.user.commune)
        elif role == 'AGENT_SOUS_PREFECTURE':
            # L'agent de sous-préfecture voit tous les utilisateurs de sa sous-préfecture
            return qs.filter(commune__sous_prefecture=request.user.commune.sous_prefecture)
        elif role == 'CITOYEN':
            # CORRECTION: Le citoyen ne voit que son propre profil - utiliser 'pk' au lieu de 'id'
            return qs.filter(pk=request.user.pk)
        else:
            return qs.none()

    # CORRECTION 2: Validation avant sauvegarde - ne pas bloquer les modifications
    # Modifier la méthode save_model pour éviter les erreurs de rôle
    def save_model(self, request, obj, form, change):
        role = getattr(obj, 'role', None)
        current_user_role = getattr(request.user, 'role', None)
        
        # Validation pour les rôles nécessitant une commune
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if not obj.commune:
                messages.error(request, 'Une commune doit être spécifiée pour ce rôle')
                return
        
        # Empêcher la modification de certains champs par des non-administrateurs
        if not request.user.is_superuser and current_user_role != 'ADMINISTRATEUR':
            if change:  # Si c'est une modification
                original_obj = self.model.objects.get(pk=obj.pk)
                # Préserver les champs sensibles
                for field in ['role', 'is_verified', 'is_staff', 'is_superuser']:
                    setattr(obj, field, getattr(original_obj, field))
        
        super().save_model(request, obj, form, change)
        
    # CORRECTION 3: Ajouter une méthode pour forcer le rafraîchissement de l'aperçu photo
    def response_change(self, request, obj):
        """
        Override pour forcer le rafraîchissement de la page après modification
        afin que l'aperçu de la photo soit mis à jour
        """
        response = super().response_change(request, obj)
        
        # Si c'est une redirection vers la même page (modification continue)
        if (hasattr(response, 'status_code') and 
            response.status_code == 302 and 
            '_continue' in request.POST):
            # Ajouter un timestamp pour forcer le rafraîchissement
            import time
            redirect_url = response['Location']
            if '?' in redirect_url:
                redirect_url += f'&t={int(time.time())}'
            else:
                redirect_url += f'?t={int(time.time())}'
            response['Location'] = redirect_url
            
        return response
    
# ========== ADMIN POUR LES STRUCTURES TERRITORIALES ==========
# Ces classes ne sont accessibles qu'aux administrateurs
class AdminOnlyMixin:
    def has_module_permission(self, request):
        return getattr(request.user, 'role', None) == 'ADMINISTRATEUR'

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):  # J'ai retiré AdminOnlyMixin pour simplifier ici
    list_display = ('nom', 'code_region', 'nombre_departements', 'modifier_lien', 'supprimer_lien')
    search_fields = ('nom', 'code_region')
    list_per_page = 6

    def nombre_departements(self, obj):
        return obj.departements.count()
    nombre_departements.short_description = 'Nb Départements'

    def modifier_lien(self, obj):
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            f'/admin/core/region/{obj.pk}/change/'
        )
    modifier_lien.short_description = 'Modifier'
    modifier_lien.allow_tags = True

    def supprimer_lien(self, obj):
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            f'/admin/core/region/{obj.pk}/delete/'
        )
    supprimer_lien.short_description = 'Supprimer'
    supprimer_lien.allow_tags = True


@admin.register(Departement)
class DepartementAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = ('nom', 'code_departement', 'region', 'nombre_sous_prefectures', 'modifier_lien', 'supprimer_lien')
    list_filter = ('region',)
    search_fields = ('nom', 'code_departement')
    list_per_page = 6

    def nombre_sous_prefectures(self, obj):
        return obj.sous_prefectures.count()
    nombre_sous_prefectures.short_description = 'Nb Sous-Préfectures'

    def modifier_lien(self, obj):
        url = reverse('admin:core_departement_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_departement_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
@admin.register(SousPrefecture)
class SousPrefectureAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = (
        'nom',
        'code_sous_prefecture',
        'departement',
        'telephone',
        'nombre_communes',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('departement__region', 'departement')
    search_fields = ('nom', 'code_sous_prefecture')
    list_per_page = 6

    def nombre_communes(self, obj):
        return obj.communes.count()
    nombre_communes.short_description = 'Nb Communes'

    def modifier_lien(self, obj):
        url = reverse('admin:core_sousprefecture_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_sousprefecture_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
@admin.register(Commune)
class CommuneAdmin(AdminOnlyMixin, admin.ModelAdmin):
    list_display = (
        'nom',
        'code_commune',
        'sous_prefecture',
        'telephone',
        'email',
        'statistiques_mois',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = (
        'sous_prefecture__departement__region',
        'sous_prefecture__departement',
        'sous_prefecture',
    )
    search_fields = ('nom', 'code_commune')
    list_per_page = 6

    def modifier_lien(self, obj):
        url = reverse('admin:core_commune_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_commune_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
    def get_queryset(self, request):
        """
        Filtre les communes selon le rôle de l'utilisateur connecté
        """
        qs = super().get_queryset(request)
        user = request.user
        
        # Les citoyens voient toutes les communes
        if user.role == 'CITOYEN':
            return qs
        
        # Les administrateurs voient toutes les communes
        elif user.role == 'ADMINISTRATEUR':
            return qs
        
        # Les agents de commune ne voient que leur commune
        elif user.role == 'AGENT_COMMUNE':
            if hasattr(user, 'commune') and user.commune:
                return qs.filter(id=user.commune.id)
            else:
                return qs.none()  # Aucune commune si pas d'association
        
        # Les maires ne voient que leur commune
        elif user.role == 'MAIRE':
            if hasattr(user, 'commune') and user.commune:
                return qs.filter(id=user.commune.id)
            else:
                return qs.none()
        
        # Les agents de sous-préfecture voient les communes de leur sous-préfecture
        elif user.role == 'AGENT_SOUS_PREFECTURE':
            if hasattr(user, 'sous_prefecture') and user.sous_prefecture:
                return qs.filter(sous_prefecture=user.sous_prefecture)
            else:
                return qs.none()
        
        # Les sous-préfets voient les communes de leur sous-préfecture
        elif user.role == 'SOUS_PREFET':
            if hasattr(user, 'sous_prefecture') and user.sous_prefecture:
                return qs.filter(sous_prefecture=user.sous_prefecture)
            else:
                return qs.none()
        
        # Par défaut, aucune commune visible
        return qs.none()
    
    def has_add_permission(self, request):
        """
        Contrôle qui peut ajouter des communes
        """
        # Seuls les administrateurs peuvent ajouter des communes
        return request.user.role in ['ADMINISTRATEUR']
    
    def has_change_permission(self, request, obj=None):
        """
        Contrôle qui peut modifier des communes
        """
        user = request.user
        
        # Les administrateurs peuvent tout modifier
        if user.role == 'ADMINISTRATEUR':
            return True
        
        # Les maires peuvent modifier leur commune
        if user.role == 'MAIRE' and obj:
            return hasattr(user, 'commune') and user.commune == obj
        
        # Les sous-préfets peuvent modifier les communes de leur sous-préfecture
        if user.role == 'SOUS_PREFET' and obj:
            return hasattr(user, 'sous_prefecture') and obj.sous_prefecture == user.sous_prefecture
        
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Contrôle qui peut supprimer des communes
        """
        # Seuls les administrateurs peuvent supprimer
        return request.user.role == 'ADMINISTRATEUR'
    
    def statistiques_mois(self, obj):
        current_month = timezone.now().month
        current_year = timezone.now().year
        stats = obj.statistiques.filter(annee=current_year, mois=current_month).first()
        if stats:
            return f"N:{stats.naissances_total} M:{stats.mariages_total} D:{stats.deces_total}"
        return "Aucune statistique"

# ========== ADMIN POUR LES PERSONNES ==========
# ========== ADMIN POUR LES PERSONNES ==========

@admin.register(Personne)
class PersonneAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'nom',
        'prenoms',
        'date_naissance',
        'sexe',
        'commune_naissance',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = (
        'sexe',
        'situation_matrimoniale',
        PersonneCommuneFilter,
    )
    search_fields = (
        'nom',
        'prenoms',
        'nom_pere',
        'nom_mere',
        'numero_unique',
    )
    date_hierarchy = 'date_naissance'
    exclude = ('user',)
    list_per_page = 10

    def modifier_lien(self, obj):
        url = reverse('admin:core_personne_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_personne_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'CITOYEN':
            # Les citoyens voient seulement les personnes qu'ils ont créées
            return qs.filter(user=request.user)
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            # Agents communaux voient les personnes de leur commune
            if hasattr(request.user, 'commune'):
                return qs.filter(commune_naissance=request.user.commune)
            return qs.none()
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Agents de sous-préfecture voient les personnes de leur sous-préfecture
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return qs.filter(commune_naissance__sous_prefecture=request.user.commune.sous_prefecture)
            return qs.none()
        # Administrateurs voient tout
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

        if not change and role == 'CITOYEN':
            obj.user = request.user

            if (obj.nom != request.user.last_name or obj.prenoms != request.user.first_name):
                messages.warning(
                    request, 
                    "Les informations ne correspondent pas à votre profil. "
                    "Veuillez vérifier les noms et prénoms."
                )

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
    list_display = (
        'numero_acte',
        'get_nom_complet',
        'commune_enregistrement',
        'agent_enregistreur',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('commune_enregistrement', 'date_enregistrement')
    search_fields = ('numero_acte', 'personne__nom', 'personne__prenoms')
    date_hierarchy = 'date_enregistrement'
    autocomplete_fields = ['personne', 'agent_enregistreur']
    actions = ['generate_pdf_action']
    list_per_page = 10
    exclude = ('numero_acte', 'numero_registre', 'page_registre')

    def modifier_lien(self, obj):
        url = reverse('admin:core_actenaissance_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_actenaissance_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'

    def generate_pdf_action(self, request, queryset):
        from core.models import DocumentNumerique
        from django.contrib import messages
        
        for acte in queryset:
            try:
                # Trouver ou créer une demande associée (simulée)
                demande, created = DemandeActe.objects.get_or_create(
                    type_acte='NAISSANCE',  # ou 'MARIAGE'/'DECES' selon la classe
                    personne_concernee=acte.personne,
                    defaults={
                        'statut': 'DELIVRE',
                        'demandeur': request.user,
                        'commune_traitement': acte.commune_enregistrement,
                    }
                )
                
                # Créer le document numérique
                doc = DocumentNumerique.objects.create(
                    demande=demande,
                    type_document='ACTE_OFFICIEL',
                )
                
                # Générer le PDF
                doc.generate_acte_pdf()
                
                messages.success(request, f"PDF généré pour l'acte {acte.numero_acte}")
            except Exception as e:
                messages.error(request, f"Erreur pour l'acte {acte.numero_acte}: {str(e)}")
    generate_pdf_action.short_description = "Générer les PDF pour les actes sélectionnés"
   
    
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
    

@admin.register(Mariage)
class MariageAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'numero_acte',
        'get_epoux',
        'get_epouse',
        'date_mariage',
        'commune_mariage',
        'regime_matrimonial',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('commune_mariage', 'date_mariage', 'regime_matrimonial')
    search_fields = ('numero_acte', 'epoux__nom', 'epouse__nom')
    date_hierarchy = 'date_mariage'
    autocomplete_fields = ['epoux', 'epouse', 'commune_mariage', 'officier_etat_civil']
    list_per_page = 10
    exclude = ('numero_acte', 'numero_registre', 'page_registre')
    actions = ['generate_pdf_action']

    def modifier_lien(self, obj):
        url = reverse('admin:core_mariage_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_mariage_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
    def generate_pdf_action(self, request, queryset):
        from core.models import DocumentNumerique
        from django.contrib import messages
        
        for acte in queryset:
            try:
                # Trouver ou créer une demande associée (simulée)
                demande, created = DemandeActe.objects.get_or_create(
                    type_acte= 'MARIAGE',
                    personne_concernee=acte.epoux,
                    defaults={
                        'statut': 'DELIVRE',
                        'demandeur': request.user,
                        'commune_traitement': acte.commune_mariage,
                    }
                )
                
                # Créer le document numérique
                doc = DocumentNumerique.objects.create(
                    demande=demande,
                    type_document='ACTE_OFFICIEL',
                )
                
                # Générer le PDF
                doc.generate_acte_pdf()
                
                messages.success(request, f"PDF généré pour l'acte {acte.numero_acte}")
            except Exception as e:
                messages.error(request, f"Erreur pour l'acte {acte.numero_acte}: {str(e)}")
    generate_pdf_action.short_description = "Générer les PDF pour les actes sélectionnés"
    
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
    list_display = (
        'numero_acte',
        'get_nom_complet',
        'date_deces',
        'commune_deces',
        'agent_enregistreur',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('commune_deces', 'date_deces')
    search_fields = ('numero_acte', 'personne__nom', 'personne__prenoms')
    date_hierarchy = 'date_deces'
    autocomplete_fields = ['personne', 'agent_enregistreur']
    exclude = ('numero_acte', 'numero_registre', 'page_registre')
    list_per_page = 10
    actions = ['generate_pdf_action']

    def modifier_lien(self, obj):
        url = reverse('admin:core_actedeces_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_actedeces_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
    def generate_pdf_action(self, request, queryset):
        from core.models import DocumentNumerique
        from django.contrib import messages
        
        for acte in queryset:
            try:
                # Trouver ou créer une demande associée (simulée)
                demande, created = DemandeActe.objects.get_or_create(
                    type_acte='DECES',
                    personne_concernee=acte.personne,
                    defaults={
                        'statut': 'DELIVRE',
                        'demandeur': request.user,
                        'commune_traitement': acte.commune_deces,
                    }
                )
                
                # Créer le document numérique
                doc = DocumentNumerique.objects.create(
                    demande=demande,
                    type_document='ACTE_OFFICIEL',
                )
                
                # Générer le PDF
                doc.generate_acte_pdf()
                
                messages.success(request, f"PDF généré pour l'acte {acte.numero_acte}")
            except Exception as e:
                messages.error(request, f"Erreur pour l'acte {acte.numero_acte}: {str(e)}")
    generate_pdf_action.short_description = "Générer les PDF pour les actes sélectionnés"
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
    
@admin.register(DemandeActe)
class DemandeActeAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'numero_demande',
        'tarif_applique',
        'get_personne_concernee',
        'demandeur',
        'statut',
        'date_demande',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = (CommuneFilter, StatutDemandeFilter, 'tarif_applique')
    search_fields = (
        'numero_demande',
        'personne_concernee__nom',
        'personne_concernee__prenoms',
        'demandeur__username',
    )
    date_hierarchy = 'date_demande'
    readonly_fields = ('numero_demande', 'date_demande')
    autocomplete_fields = ['demandeur', 'personne_concernee', 'agent_traitant']
    list_per_page = 10

    def actions_paiement(self, obj):
        if obj.statut_paiement != 'PAYE':
            url = reverse('initiate_payment', args=[obj.id])
            return format_html(
                '<a class="button" href="{}">💳 Payer avec CinetPay</a>',
                url
            )
        else:
            return "✅ Payé"
    
    actions_paiement.short_description = "Actions de paiement"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:demande_id>/pay/', self.admin_site.admin_view(self.initiate_payment), name='initiate_payment'),
        ]
        return custom_urls + urls
    
    def initiate_payment(self, request, demande_id):
        from .views.cinetpay_views import initiate_payment_view
        return initiate_payment_view(request, demande_id)
    def modifier_lien(self, obj):
        url = reverse('admin:core_demandeacte_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_demandeacte_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
    def get_readonly_fields(self, request, obj=None):
        """Champs non modifiables selon le rôle"""
        readonly = super().get_readonly_fields(request, obj)
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            return readonly + (
                'statut', 'agent_validateur', 'agent_traitant',
                'commentaire_agent', 'commentaire_rejet',
                'date_validation_preliminaire', 'date_traitement',
                'date_delivrance', 'numero_suivi', 'montant_total',
                'montant_calcule', 'paiement_requis'
            )
        # Les agents ont accès à tous les champs de modification
        return readonly

    def get_fields(self, request, obj=None):
        """Champs affichés selon le rôle"""
        fields = super().get_fields(request, obj)
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            return [f for f in fields if f not in [
                'statut', 'agent_validateur', 'agent_traitant',
                'commentaire_agent', 'commentaire_rejet',
                'date_validation_preliminaire', 'date_traitement',
                'date_delivrance', 'numero_suivi', 'montant_total',
                'montant_calcule', 'paiement_requis'
            ]]
        # Les agents voient tous les champs
        return fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'CITOYEN':
            # Les citoyens voient seulement leurs demandes
            return qs.filter(demandeur=request.user)
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            # Agents communaux voient les demandes de leur commune
            if hasattr(request.user, 'commune'):
                return qs.filter(commune_traitement=request.user.commune)
            return qs.none()
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Agents de sous-préfecture voient les demandes de leur sous-préfecture
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return qs.filter(commune_traitement__sous_prefecture=request.user.commune.sous_prefecture)
            return qs.none()
        # Administrateurs voient tout
        return qs

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            return False  # Les citoyens ne peuvent pas modifier
        elif role == 'ADMINISTRATEUR':
            return True  # Accès complet
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            # Peut modifier les demandes de sa commune
            if hasattr(request.user, 'commune') and obj.personne_concernee:
                return obj.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            # Peut modifier les demandes de sa sous-préfecture
            if (hasattr(request.user, 'commune') and 
                hasattr(request.user.commune, 'sous_prefecture') and 
                obj.personne_concernee):
                return obj.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        
        return super().has_change_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            if obj is None:
                return True
            return obj.demandeur == request.user
        elif role == 'ADMINISTRATEUR':
            return True
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            # Peut voir les demandes de sa commune
            if hasattr(request.user, 'commune') and obj.personne_concernee:
                return obj.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            # Peut voir les demandes de sa sous-préfecture
            if (hasattr(request.user, 'commune') and 
                hasattr(request.user.commune, 'sous_prefecture') and 
                obj.personne_concernee):
                return obj.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        # Tous les rôles authentifiés peuvent créer une demande
        return hasattr(request.user, 'role')

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            return False
        elif role == 'ADMINISTRATEUR':
            return True
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            # Peut supprimer les demandes de sa commune
            if hasattr(request.user, 'commune') and obj.personne_concernee:
                return obj.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            # Peut supprimer les demandes de sa sous-préfecture
            if (hasattr(request.user, 'commune') and 
                hasattr(request.user.commune, 'sous_prefecture') and 
                obj.personne_concernee):
                return obj.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        role = getattr(request.user, 'role', None)

        if db_field.name == "personne_concernee":
            if role == 'ADMINISTRATEUR':
                pass  # Accès à toutes les personnes
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                if hasattr(request.user, 'commune'):
                    kwargs["queryset"] = Personne.objects.filter(
                        commune_naissance=request.user.commune
                    )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
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

        elif db_field.name == "agent_traitant":
            # Les agents peuvent s'assigner ou assigner d'autres agents de leur structure
            if role in ['AGENT_COMMUNE', 'MAIRE']:
                if hasattr(request.user, 'commune'):
                    kwargs["queryset"] = User.objects.filter(
                        role__in=['AGENT_COMMUNE', 'MAIRE'],
                        commune=request.user.commune
                    )
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                    kwargs["queryset"] = User.objects.filter(
                        role__in=['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE'],
                        commune__sous_prefecture=request.user.commune.sous_prefecture
                    )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        role = getattr(request.user, 'role', None)
        
        # Auto-assigner le demandeur pour les citoyens
        if role == 'CITOYEN':
            initial['demandeur'] = request.user
        # Auto-assigner l'agent traitant pour les agents
        elif role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            initial['agent_traitant'] = request.user
            
        return initial

    def get_personne_concernee(self, obj):
        if obj.personne_concernee:
            return f"{obj.personne_concernee.nom} {obj.personne_concernee.prenoms}"
        return "-"
    get_personne_concernee.short_description = 'Personne concernée'

    def action_buttons(self, obj):
        from django.urls import reverse
        from django.utils.safestring import mark_safe

        if not hasattr(self, 'request'):
            return ""
        
        role = getattr(self.request.user, 'role', None)

        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj.statut == 'EN_ATTENTE':
                url = reverse('admin:core_demandeacte_change', args=[obj.pk])
                return mark_safe(f'<a href="{url}" class="button">Traiter</a>')
            elif obj.statut == 'DELIVRE':
                return mark_safe('<a href="#" class="button">Générer PDF</a>')
        elif role == 'CITOYEN' and obj.statut == 'DELIVRE':
            return mark_safe('<a href="#" class="button">Télécharger PDF</a>')
        
        return ""
    action_buttons.short_description = 'Actions'

    def changelist_view(self, request, extra_context=None):
        self.request = request
        return super().changelist_view(request, extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            return {}  # Pas d'actions pour les citoyens
        
        # Actions disponibles pour tous les agents
        if role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE', 'ADMINISTRATEUR']:
            if hasattr(self, 'approuver_demandes'):
                actions['approuver_demandes'] = (self.approuver_demandes, 'approuver_demandes', self.approuver_demandes.short_description)
            if hasattr(self, 'rejeter_demandes'):
                actions['rejeter_demandes'] = (self.rejeter_demandes, 'rejeter_demandes', self.rejeter_demandes.short_description)
            if hasattr(self, 'marquer_delivrees'):
                actions['marquer_delivrees'] = (self.marquer_delivrees, 'marquer_delivrees', self.marquer_delivrees.short_description)
        
        return actions

    def approuver_demandes(self, request, queryset):
        # Filtrer pour ne traiter que les demandes de sa juridiction
        qs_filtered = self._filter_queryset_by_jurisdiction(request, queryset)
        updated = qs_filtered.filter(statut='EN_ATTENTE').update(
            statut='APPROUVE',
            agent_traitant=request.user,
            date_traitement=timezone.now()
        )
        self.message_user(request, f"{updated} demande(s) approuvée(s).")
    approuver_demandes.short_description = "Approuver les demandes sélectionnées"

    def rejeter_demandes(self, request, queryset):
        qs_filtered = self._filter_queryset_by_jurisdiction(request, queryset)
        updated = qs_filtered.filter(statut='EN_ATTENTE').update(
            statut='REJETE',
            agent_traitant=request.user,
            date_traitement=timezone.now()
        )
        self.message_user(request, f"{updated} demande(s) rejetée(s).")
    rejeter_demandes.short_description = "Rejeter les demandes sélectionnées"

    def marquer_delivrees(self, request, queryset):
        qs_filtered = self._filter_queryset_by_jurisdiction(request, queryset)
        updated = qs_filtered.filter(statut='APPROUVE').update(
            statut='DELIVRE',
            date_delivrance=timezone.now()
        )
        self.message_user(request, f"{updated} demande(s) marquée(s) comme délivrée(s).")
    marquer_delivrees.short_description = "Marquer comme délivrées"

    def _filter_queryset_by_jurisdiction(self, request, queryset):
        """Filtre le queryset selon la juridiction de l'utilisateur"""
        role = getattr(request.user, 'role', None)
        
        if role == 'ADMINISTRATEUR':
            return queryset
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if hasattr(request.user, 'commune'):
                return queryset.filter(personne_concernee__commune_naissance=request.user.commune)
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return queryset.filter(personne_concernee__commune_naissance__sous_prefecture=request.user.commune.sous_prefecture)
        
        return queryset.none()

    def has_module_permission(self, request):
        return hasattr(request.user, 'role')


from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib import messages
from django.utils.safestring import mark_safe
from .models import Paiement, DemandeActe


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = (
        'reference_transaction', 
        'get_demande_acte', 
        'get_demandeur',
        'montant_total_display',
        'get_statut_display_colored', 
        'mode_paiement',
        'date_paiement',
        'duree_traitement_display',
        'payment_actions'
    )
    
    list_filter = (
        'statut', 
        'mode_paiement', 
        'date_creation', 
        'date_paiement',
        'date_validation'
    )
    
    search_fields = (
        'reference_transaction', 
        'transaction_id',
        'demande_acte__id',
        'demande_acte__demandeur__first_name',
        'demande_acte__demandeur__last_name'
    )
    
    ordering = ('-date_creation',)
    list_per_page = 25
    date_hierarchy = 'date_creation'
    
    readonly_fields = (
        'reference_transaction',
        'date_creation',
        'date_validation',
        'date_confirmation',
        'date_paiement',
        'date_remboursement',
        'duree_traitement',
        'agent_confirmateur'
    )
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'demande_acte',
                'reference_transaction',
                'transaction_id',
                'statut',
                'mode_paiement'
            )
        }),
        ('Montants', {
            'fields': (
                'montant',
                'montant_timbres',
                'montant_total'
            )
        }),
        ('Informations de paiement', {
            'fields': (
                'methode_paiement',
                'numero_telephone'
            ),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': (
                'date_creation',
                'date_paiement',
                'date_validation',
                'date_confirmation',
                'date_expiration',
                'date_remboursement'
            ),
            'classes': ('collapse',)
        }),
        ('Traitement', {
            'fields': (
                'agent_confirmateur',
                'code_erreur',
                'message_erreur',
                'commentaire'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return qs
        elif role == 'CITOYEN':
            return qs.filter(demande_acte__demandeur=request.user)
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if hasattr(request.user, 'commune'):
                return qs.filter(demande_acte__personne_concernee__commune_naissance=request.user.commune)
            return qs.none()
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return qs.filter(demande_acte__personne_concernee__commune_naissance__sous_prefecture=request.user.commune.sous_prefecture)
            return qs.none()
        return qs.none()

    def has_view_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            if obj is None:
                return True
            return obj.demande_acte.demandeur == request.user
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            return False  # Les citoyens ne peuvent pas modifier les paiements
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            return False  # Les citoyens ne peuvent pas supprimer
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        role = getattr(request.user, 'role', None)

        if db_field.name == 'demande_acte':
            if role == 'ADMINISTRATEUR':
                kwargs['queryset'] = DemandeActe.objects.all()
            elif role == 'CITOYEN':
                kwargs['queryset'] = DemandeActe.objects.filter(
                    demandeur=request.user
                )
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                if hasattr(request.user, 'commune'):
                    kwargs['queryset'] = DemandeActe.objects.filter(
                        personne_concernee__commune_naissance=request.user.commune
                    )
                else:
                    kwargs['queryset'] = DemandeActe.objects.none()
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                    kwargs['queryset'] = DemandeActe.objects.filter(
                        personne_concernee__commune_naissance__sous_prefecture=request.user.commune.sous_prefecture
                    )
                else:
                    kwargs['queryset'] = DemandeActe.objects.none()
            else:
                kwargs['queryset'] = DemandeActe.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        role = getattr(request.user, 'role', None)
        
        if role == 'CITOYEN':
            # Pour les citoyens, tous les champs sont en lecture seule
            return [f.name for f in self.model._meta.fields] + ['payment_interface_link']
        elif role in ['AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Pour les agents, certains champs restent modifiables
            readonly_fields.extend([
                'reference_transaction',
                'transaction_id',
                'date_creation',
                'date_paiement'
            ])
        return readonly_fields

    def payment_interface_link(self, obj):
        if obj.statut == 'VALIDE':
            url = reverse('admin:payment_interface', args=[obj.pk])
            return format_html('<a class="button" href="{}">Accéder à l\'interface</a>', url)
        return "Non disponible"
    payment_interface_link.short_description = "Interface de paiement"

    def has_module_permission(self, request):
        # Tous les rôles peuvent accéder au module
        return hasattr(request.user, 'role')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return qs
        elif role == 'CITOYEN':
            return qs.filter(demande_acte__demandeur=request.user)
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if hasattr(request.user, 'commune'):
                return qs.filter(demande_acte__personne_concernee__commune_naissance=request.user.commune)
            return qs.none()
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return qs.filter(demande_acte__personne_concernee__commune_naissance__sous_prefecture=request.user.commune.sous_prefecture)
            return qs.none()
        return qs.none()

    def has_view_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            if obj is None:
                return True
            return obj.demande_acte.demandeur == request.user
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            if obj is None:
                return True
            # Un citoyen peut modifier seulement ses paiements en attente ou échoués
            return (obj.demande_acte.demandeur == request.user and 
                   obj.statut in ['EN_ATTENTE', 'ECHEC'])
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def has_delete_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)

        if request.user.is_superuser or role == 'ADMINISTRATEUR':
            return True
        elif role == 'CITOYEN':
            # Les citoyens ne peuvent pas supprimer leurs paiements
            return False
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            if obj is None:
                return True
            if hasattr(request.user, 'commune') and obj.demande_acte.personne_concernee:
                return obj.demande_acte.personne_concernee.commune_naissance == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            if obj is None:
                return True
            if (hasattr(request.user, 'commune') and
                hasattr(request.user.commune, 'sous_prefecture') and
                obj.demande_acte.personne_concernee):
                return obj.demande_acte.personne_concernee.commune_naissance.sous_prefecture == request.user.commune.sous_prefecture
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        role = getattr(request.user, 'role', None)

        if db_field.name == 'demande_acte':
            if role == 'ADMINISTRATEUR':
                kwargs['queryset'] = DemandeActe.objects.filter(
                    statut='EN_ATTENTE_PAIEMENT'
                ).exclude(paiement__isnull=False)
            elif role == 'CITOYEN':
                kwargs['queryset'] = DemandeActe.objects.filter(
                    demandeur=request.user,
                    statut='EN_ATTENTE_PAIEMENT'
                ).exclude(paiement__isnull=False)
            elif role in ['AGENT_COMMUNE', 'MAIRE']:
                if hasattr(request.user, 'commune'):
                    kwargs['queryset'] = DemandeActe.objects.filter(
                        personne_concernee__commune_naissance=request.user.commune,
                        statut='EN_ATTENTE_PAIEMENT'
                    ).exclude(paiement__isnull=False)
                else:
                    kwargs['queryset'] = DemandeActe.objects.none()
            elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
                if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                    kwargs['queryset'] = DemandeActe.objects.filter(
                        personne_concernee__commune_naissance__sous_prefecture=request.user.commune.sous_prefecture,
                        statut='EN_ATTENTE_PAIEMENT'
                    ).exclude(paiement__isnull=False)
                else:
                    kwargs['queryset'] = DemandeActe.objects.none()
            else:
                kwargs['queryset'] = DemandeActe.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/pay_cinetpay/', 
                 self.admin_site.admin_view(self.pay_cinetpay), 
                 name='pay_cinetpay'),
            path('<int:object_id>/payment_interface/', 
                 self.admin_site.admin_view(self.payment_interface), 
                 name='payment_interface'),
            path('<int:object_id>/verify_payment/', 
                 self.admin_site.admin_view(self.verify_payment), 
                 name='verify_payment'),
            path('<int:object_id>/confirm_payment/', 
                 self.admin_site.admin_view(self.confirm_payment), 
                 name='confirm_payment'),
            path('<int:object_id>/cancel_payment/', 
                 self.admin_site.admin_view(self.cancel_payment), 
                 name='cancel_payment'),
            path('<int:object_id>/refund_payment/', 
                 self.admin_site.admin_view(self.refund_payment), 
                 name='refund_payment'),
            path('payment_success/<int:object_id>/', 
                 self.payment_success, 
                 name='payment_success'),
            path('payment_cancel/<int:object_id>/', 
                 self.payment_cancel, 
                 name='payment_cancel'),
            path('payment_notify/<int:object_id>/', 
                 self.payment_notify, 
                 name='payment_notify'),
        ]
        return custom_urls + urls

    # Méthodes d'affichage personnalisées
    def get_demande_acte(self, obj):
        if obj.demande_acte:
            return f"{obj.demande_acte.type_acte} - #{obj.demande_acte.id}"
        return "-"
    get_demande_acte.short_description = 'Demande'

    def get_demandeur(self, obj):
        if obj.demande_acte and obj.demande_acte.demandeur:
            return obj.demande_acte.demandeur.get_full_name()
        return "-"
    get_demandeur.short_description = 'Demandeur'

    def montant_total_display(self, obj):
        montant = obj.montant_total or obj.montant
        if montant:
            return f"{montant:,.0f} FCFA"
        return "-"
    montant_total_display.short_description = 'Montant Total'

    def get_statut_display_colored(self, obj):
        colors = {
            'EN_ATTENTE': '#ffc107',     # Orange
            'VALIDE': '#28a745',         # Vert
            'ECHEC': '#dc3545',          # Rouge
            'ANNULE': '#6f42c1',         # Violet
            'REMBOURSE': '#fd7e14',      # Orange foncé
        }
        color = colors.get(obj.statut, '#6c757d')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.get_statut_display()}</span>')
    get_statut_display_colored.short_description = 'Statut'

    def duree_traitement_display(self, obj):
        duree = obj.duree_traitement
        if duree:
            total_seconds = int(duree.total_seconds())
            heures, reste = divmod(total_seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            return f"{heures}h {minutes}m {secondes}s"
        return "-"
    duree_traitement_display.short_description = "Durée traitement"

    def payment_actions(self, obj):
        buttons = []
        
        if obj.statut == 'EN_ATTENTE':
            # Bouton pour payer
            pay_url = reverse('admin:pay_cinetpay', args=[obj.pk])
            buttons.append(f'<a class="button" href="{pay_url}">Payer</a>')
            
            # Bouton pour annuler
            cancel_url = reverse('admin:cancel_payment', args=[obj.pk])
            buttons.append(f'<a class="button" href="{cancel_url}" style="background-color: #dc3545;">Annuler</a>')
        
        elif obj.statut == 'EN_COURS':
            # Bouton pour vérifier
            verify_url = reverse('admin:verify_payment', args=[obj.pk])
            buttons.append(f'<a class="button" href="{verify_url}">Vérifier</a>')
            
            # Bouton pour confirmer manuellement
            confirm_url = reverse('admin:confirm_payment', args=[obj.pk])
            buttons.append(f'<a class="button" href="{confirm_url}" style="background-color: #28a745;">Confirmer</a>')
        
        elif obj.statut == 'VALIDE':
            # Bouton pour l'interface de paiement
            interface_url = reverse('admin:payment_interface', args=[obj.pk])
            buttons.append(f'<a class="button" href="{interface_url}">Interface</a>')
            
            # Bouton pour rembourser
            refund_url = reverse('admin:refund_payment', args=[obj.pk])
            buttons.append(f'<a class="button" href="{refund_url}" style="background-color: #fd7e14;">Rembourser</a>')
        
        return mark_safe(' '.join(buttons))
    payment_actions.short_description = 'Actions'
    payment_actions.allow_tags = True

    # Méthodes de gestion des vues personnalisées
    def pay_cinetpay(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        if paiement.statut not in ['EN_ATTENTE', 'ECHEC']:
            self.message_user(request, 
                            f"Ce paiement ne peut pas être payé (statut: {paiement.get_statut_display()})", 
                            messages.ERROR)
            return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))
        
        # Logique pour rediriger vers CinetPay
        url_paiement = f'https://cinetpay.example.com/pay?ref={paiement.reference_transaction}'
        return redirect(url_paiement)

    def payment_interface(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        # AJOUTER cette configuration
        cinetpay_config = {
            'api_key': settings.CINETPAY_API_KEY,  # À définir dans settings.py
            'site_id': settings.CINETPAY_SITE_ID,  # À définir dans settings.py
        }
        
        context = {
            'paiement': paiement,
            'title': f'Interface de paiement - {paiement.reference_transaction}',
            'cinetpay_config': cinetpay_config,  # AJOUTER cette ligne
        }
        return render(request, 'admin/core/paiement/payment_interface.html', context)

    def verify_payment(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        # AJOUTER : Gestion des appels AJAX
        if request.method == 'POST' and request.headers.get('Content-Type') == 'application/json':
            import json
            try:
                data = json.loads(request.body)
                verify_only = data.get('verify_only', False)
                
                if paiement.statut not in ['EN_ATTENTE', 'EN_COURS']:
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Ce paiement ne peut pas être vérifié (statut: {paiement.get_statut_display()})"
                    }, status=400)
                
                # Logique de vérification du paiement
                success = self._verifier_paiement_externe(paiement)
                
                if success:
                    paiement.confirmer(agent=request.user)
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Paiement confirmé avec succès.'
                    })
                else:
                    return JsonResponse({
                        'status': 'pending',
                        'message': 'Le paiement est toujours en attente ou a échoué.'
                    })
                    
            except json.JSONDecodeError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Format JSON invalide'
                }, status=400)
        
        # GARDER : Code original pour les appels HTTP normaux
        if paiement.statut not in ['EN_ATTENTE', 'EN_COURS']:
            self.message_user(request, 
                            f"Ce paiement ne peut pas être vérifié (statut: {paiement.get_statut_display()})", 
                            messages.ERROR)
            return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))
        
        success = self._verifier_paiement_externe(paiement)
        
        if success:
            paiement.confirmer(agent=request.user)
            self.message_user(request, "Paiement confirmé avec succès.", messages.SUCCESS)
        else:
            self.message_user(request, "Le paiement est toujours en attente ou a échoué.", messages.WARNING)
        
        return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))

    def confirm_payment(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        if not paiement.peut_etre_confirme:
            self.message_user(request, 
                            f"Ce paiement ne peut pas être confirmé (statut: {paiement.get_statut_display()})", 
                            messages.ERROR)
            return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))
        
        try:
            paiement.confirmer(agent=request.user)
            self.message_user(request, "Paiement confirmé manuellement avec succès.", messages.SUCCESS)
        except ValueError as e:
            self.message_user(request, str(e), messages.ERROR)
        
        return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))

    def cancel_payment(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        if not paiement.peut_etre_annule:
            self.message_user(request, 
                            f"Ce paiement ne peut pas être annulé (statut: {paiement.get_statut_display()})", 
                            messages.ERROR)
            return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))
        
        motif = request.GET.get('motif', 'Annulation manuelle depuis l\'administration')
        
        if paiement.annuler(motif=motif):
            self.message_user(request, "Paiement annulé avec succès.", messages.SUCCESS)
        else:
            self.message_user(request, "Impossible d'annuler ce paiement.", messages.ERROR)
        
        return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))

    def refund_payment(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        if not paiement.peut_etre_rembourse:
            self.message_user(request, 
                            f"Ce paiement ne peut pas être remboursé (statut: {paiement.get_statut_display()})", 
                            messages.ERROR)
            return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))
        
        motif = request.GET.get('motif', 'Remboursement depuis l\'administration')
        
        try:
            paiement.rembourser(agent=request.user, motif=motif)
            self.message_user(request, "Paiement remboursé avec succès.", messages.SUCCESS)
        except ValueError as e:
            self.message_user(request, str(e), messages.ERROR)
        
        return HttpResponseRedirect(reverse('admin:core_paiement_change', args=[paiement.pk]))

    def _verifier_paiement_externe(self, paiement):
        """
        Méthode pour vérifier le paiement auprès du service externe
        """
        try:
            import requests
            from django.conf import settings
            
            # Appel API réel vers CinetPay
            response = requests.post(
                'https://api-checkout.cinetpay.com/v2/payment/check',
                json={
                    'apikey': settings.CINETPAY_API_KEY,
                    'site_id': settings.CINETPAY_SITE_ID,
                    'transaction_id': paiement.reference_transaction
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('status') == 'ACCEPTED'
            
        except Exception as e:
            # Log l'erreur en production
            pass
        
        # Fallback - simulation pour le développement
        import random
        return random.choice([True, False])

    # Callbacks de paiement
    def payment_success(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        try:
            paiement.confirmer()
            return HttpResponse("Paiement réussi et confirmé !")
        except ValueError as e:
            return HttpResponse(f"Erreur lors de la confirmation : {str(e)}", status=400)

    def payment_cancel(self, request, object_id):
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        if paiement.peut_etre_annule:
            paiement.annuler(motif="Annulation par l'utilisateur")
        
        return HttpResponse("Paiement annulé.")

    def payment_notify(self, request, object_id):
        """Callback de notification pour les webhooks"""
        paiement = get_object_or_404(Paiement, pk=object_id)
        
        # Traiter les données de notification
        # En fonction de l'API de paiement utilisée
        
        return HttpResponse("Notification reçue.", status=200)
    # Méthodes pour gérer success/cancel/notify peuvent être similaires,
# ========== ADMIN POUR LES TARIFS ==========
@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = (
        'type_acte',
        'prix_unitaire',
        'timbre_fiscal',
        'get_prix_total',
        'actif',
        'date_application',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('actif', 'date_application')
    list_per_page = 5

    def modifier_lien(self, obj):
        url = reverse('admin:core_tarif_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; '
            'border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_tarif_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; '
            'border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
    def get_prix_total(self, obj):
        return obj.prix_unitaire + obj.timbre_fiscal
    get_prix_total.short_description = 'Prix Total'
    
    def has_module_permission(self, request):
        role = getattr(request.user, 'role', None)
        return role in ['ADMINISTRATEUR', 'AGENT_COMMUNE', 'MAIRE', 'SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']

# ========== ADMIN POUR LES STATISTIQUES ==========
@admin.register(Statistique)
class StatistiqueAdmin(RoleBasedQuerysetMixin, admin.ModelAdmin):
    list_display = (
        'commune',
        'mois',
        'annee',
        'naissances_total',
        'mariages_total',
        'deces_total',
        'revenus_total',
        'modifier_lien',
        'supprimer_lien',
    )
    list_filter = ('annee', 'mois', 'commune')
    readonly_fields = ('date_creation',)
    list_per_page = 5

    def modifier_lien(self, obj):
        url = reverse('admin:core_statistique_change', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FFD700; color:black; padding:4px 8px; '
            'border-radius:4px; text-decoration:none;" href="{}">Modifier</a>',
            url
        )
    modifier_lien.short_description = 'Modifier'

    def supprimer_lien(self, obj):
        url = reverse('admin:core_statistique_delete', args=[obj.pk])
        return format_html(
            '<a style="background-color:#FF0000; color:white; padding:4px 8px; '
            'border-radius:4px; text-decoration:none;" href="{}">Supprimer</a>',
            url
        )
    supprimer_lien.short_description = 'Supprimer'
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
    list_per_page = 10
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
class DocumentNumeriqueAdmin(admin.ModelAdmin):
    list_display = ('demande','type_document', 'nom_fichier', 'date_creation', 'signature_status', 'download_link')
    search_fields = ['type_document', 'nom_fichier','demande__numero_demande', 'demande__commune_traitement__nom',] 
    list_filter = ('type_document', 'nom_fichier','demande__numero_demande', 'demande__commune_traitement__nom',) # <= Ajout ici
    readonly_fields = ('signature_status', 'verify_signature_button')
    actions = ['generate_pdf_action', 'sign_documents_action']
    list_per_page = 15
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        role = getattr(request.user, 'role', None)

        if role == 'CITOYEN':
            # Les citoyens voient seulement leurs documents
            return qs.filter(demande__demandeur=request.user)
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            # Agents communaux voient les documents de leur commune
            if hasattr(request.user, 'commune'):
                return qs.filter(demande__commune_traitement=request.user.commune)
            return qs.none()
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            # Agents de sous-préfecture voient les documents de leur sous-préfecture
            if hasattr(request.user, 'commune') and hasattr(request.user.commune, 'sous_prefecture'):
                return qs.filter(demande__commune_traitement__sous_prefecture=request.user.commune.sous_prefecture)
            return qs.none()
        # Administrateurs voient tout
        return qs

    def signature_status(self, obj):
        if obj.signature_numerique:
            return "Signé" if obj.verify_signature() else "Signature invalide"
        return "Non signé"
    signature_status.short_description = "Statut signature"

    def verify_signature_button(self, obj):
        if not obj.fichier or not obj.signature_numerique:
            return "Aucune signature à vérifier"
        
        verified = obj.verify_signature()
        color = "green" if verified else "red"
        text = "Signature valide" if verified else "Signature invalide"
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{text}</span>')
    verify_signature_button.short_description = "Vérification signature"

    def download_link(self, obj):
        if obj.fichier:
            url = reverse('admin:download_document', args=[obj.pk])
            return mark_safe(f'<a href="{url}">Télécharger</a>')
        return "Aucun fichier"
    download_link.short_description = "Action"

    def generate_pdf_action(self, request, queryset):
        for doc in queryset:
            try:
                doc.generate_acte_pdf()
                self.message_user(request, f"PDF généré pour {doc.demande}")
            except Exception as e:
                self.message_user(request, f"Erreur pour {doc.demande}: {str(e)}", level='ERROR')
    generate_pdf_action.short_description = "Générer les PDF sélectionnés"

    def sign_documents_action(self, request, queryset):
        for doc in queryset:
            try:
                if doc.fichier:
                    doc.sign_document()
                    doc.save()
                    self.message_user(request, f"Document signé pour {doc.demande}")
                else:
                    self.message_user(request, f"Aucun fichier pour {doc.demande}", level='WARNING')
            except Exception as e:
                self.message_user(request, f"Erreur pour {doc.demande}: {str(e)}", level='ERROR')
    sign_documents_action.short_description = "Signer les documents sélectionnés"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/download/', self.admin_site.admin_view(self.download_document), name='download_document'),
        ]
        return custom_urls + urls

    def download_document(self, request, object_id, *args, **kwargs):
        from django.http import FileResponse
        doc = DocumentNumerique.objects.get(pk=object_id)
        if doc.fichier:
            response = FileResponse(doc.fichier.open('rb'))
            response['Content-Disposition'] = f'attachment; filename="{doc.nom_fichier}"'
            return response
        from django.contrib import messages
        messages.error(request, "Aucun fichier à télécharger")
        from django.shortcuts import redirect
        return redirect('admin:core_documentnumerique_changelist')
    

    def has_module_permission(self, request):
        # Tous les rôles peuvent accéder au module
        return hasattr(request.user, 'role')

    def has_add_permission(self, request):
        return request.user.role != 'CITOYEN'  # Seuls les agents et admin peuvent ajouter

    def has_change_permission(self, request, obj=None):
        role = getattr(request.user, 'role', None)
        if role == 'CITOYEN':
            return False  # Les citoyens ne peuvent pas modifier les documents
        elif role in ['AGENT_COMMUNE', 'MAIRE']:
            return obj is not None and obj.demande.commune_traitement == request.user.commune
        elif role in ['SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
            return (obj is not None and 
                   hasattr(request.user, 'commune') and 
                   hasattr(request.user.commune, 'sous_prefecture') and
                   obj.demande.commune_traitement.sous_prefecture == request.user.commune.sous_prefecture)
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.role != 'CITOYEN'  # Interdit de supprimer


    def has_view_permission(self, request, obj=None):
        if request.user.role == 'CITOYEN':
            return True

 
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
            demande_acte__demandeur=request.user

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



