from django.shortcuts import render, get_object_or_404,redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from .models import DemandeActe
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .admin import get_dashboard_data
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from .models import User

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import DemandeActe, Paiement, DocumentNumerique, ActeNaissance
import os
from datetime import datetime


@staff_member_required
def change_demande_status(request, demande_id, status):
    if request.method == 'POST':
        demande = get_object_or_404(DemandeActe, id=demande_id)
        
        # Vérifier les permissions
        if not request.user.has_perm('core.change_demandeacte'):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Changer le statut
        demande.statut = status
        demande.agent_traitant = request.user
        demande.date_traitement = timezone.now()
        demande.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@staff_member_required
def statistiques_view(request):
    # Logique pour les statistiques
    context = {
        'title': 'Statistiques État Civil',
        # Ajouter vos données statistiques ici
    }
    return render(request, 'admin/statistiques.html', context)

@staff_member_required
def rapports_view(request):
    # Logique pour les rapports
    context = {
        'title': 'Rapports État Civil',
        # Ajouter vos données de rapport ici
    }
    return render(request, 'admin/rapports.html', context)

@staff_member_required
def demandes_aujourd_hui_view(request):
    demandes = DemandeActe.objects.filter(
        date_demande__date=timezone.now().date()
    )
    context = {
        'title': 'Demandes du Jour',
        'demandes': demandes,
    }
    return render(request, 'admin/demandes_jour.html', context)


@staff_member_required
def approuver_demande(request, pk):
    demande = get_object_or_404(DemandeActe, pk=pk)
    if demande.statut == 'EN_ATTENTE':
        demande.statut = 'APPROUVEE'
        demande.save()
        messages.success(request, "Demande approuvée avec succès.")
    return redirect(request.META.get('HTTP_REFERER'))

@staff_member_required
def rejeter_demande(request, pk):
    demande = get_object_or_404(DemandeActe, pk=pk)
    if demande.statut == 'EN_ATTENTE':
        demande.statut = 'REJETEE'
        demande.save()
        messages.success(request, "Demande rejetée.")
    return redirect(request.META.get('HTTP_REFERER'))

@staff_member_required
def delivrer_demande(request, pk):
    demande = get_object_or_404(DemandeActe, pk=pk)
    if demande.statut == 'APPROUVEE':
        demande.statut = 'DELIVREE'
        demande.save()
        messages.success(request, "Demande marquée comme délivrée.")
    return redirect(request.META.get('HTTP_REFERER'))

def home(request):
    return render(request, "home.html")




@login_required
def dashboard(request):
    role = request.user.role
    data = get_dashboard_data(request.user)
    
    if role == 'ADMINISTRATEUR':
        template = 'dashboards/admin.html'
    elif role in ['AGENT_COMMUNE', 'MAIRE','SOUS_PREFET', 'AGENT_SOUS_PREFECTURE']:
        template = 'dashboards/agent.html'
    elif role == 'CITOYEN':
        template = 'dashboards/citoyen.html'
    else:
        return redirect('admin:index')  # Par défaut
    
    return render(request, template, {'data': data})


# core/views.py
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views

class HelpGuideView(TemplateView):
    template_name = 'admin/help_guide.html'

class TarifsView(TemplateView):
    template_name = 'admin/tarifs.html'

class ContactView(TemplateView):
    template_name = 'admin/contact.html'

@login_required
def process_payment_view(request, demande_id):
    """Vue pour le traitement du paiement d'une demande"""
    demande = get_object_or_404(DemandeActe, id=demande_id, demandeur=request.user)
    
    if demande.statut != 'APPROUVE':
        return HttpResponse("Cette demande n'est pas éligible au paiement", status=403)
    
    if request.method == 'POST':
        # Traitement du paiement (simulé)
        paiement = Paiement.objects.create(
            demande=demande,
            montant=demande.tarif_total(),
            methode_paiement=request.POST.get('methode', 'MOBILE_MONEY'),
            statut='CONFIRME'
        )
        
        # Mise à jour du statut de la demande
        demande.statut = 'DELIVRE'
        demande.save()
        
        # Génération du document (simulée)
        doc = DocumentNumerique.objects.create(
            demande=demande,
            type_document='ACTE_FINAL',
            fichier='actes/acte_{}.pdf'.format(demande.id)
        )
        
        return redirect('admin:core_demandeacte_change', demande.id)
    
    # Afficher le formulaire de paiement
    context = {
        'demande': demande,
        'tarif': demande.tarif_total(),
    }
    return render(request, 'citoyen/paiement.html', context)

@login_required
def download_acte_view(request, demande_id):
    """Vue pour télécharger un acte délivré"""
    demande = get_object_or_404(DemandeActe, id=demande_id, demandeur=request.user)
    
    if demande.statut != 'DELIVRE':
        return HttpResponse("Cet acte n'est pas disponible", status=403)
    
    try:
        document = demande.documentnumerique_set.get(type_document='ACTE_FINAL')
        file_path = os.path.join(settings.MEDIA_ROOT, str(document.fichier))
        
        if os.path.exists(file_path):
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="acte_{demande.numero_demande}.pdf"'
            return response
    
    except DocumentNumerique.DoesNotExist:
        pass
    
    return HttpResponse("Document non trouvé", status=404)

@login_required
def duplicate_demande_view(request, demande_id):
    """Vue pour dupliquer une demande rejetée"""
    original = get_object_or_404(DemandeActe, id=demande_id, demandeur=request.user)
    
    if original.statut != 'REJETE':
        return HttpResponse("Seules les demandes rejetées peuvent être refaites", status=403)
    
    nouvelle_demande = DemandeActe.objects.create(
        demandeur=request.user,
        type_acte=original.type_acte,
        personne_concernee=original.personne_concernee,
        commune_traitement=original.commune_traitement,
        nombre_copies=original.nombre_copies,
        # ... autres champs à copier
        statut='EN_ATTENTE'
    )
    
    return redirect('admin:core_demandeacte_change', nouvelle_demande.id)



from django.contrib.auth.views import LoginView

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    success_url = reverse_lazy('admin:index')

    def get_success_url(self):
        return reverse_lazy('admin:index') 

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'CITOYEN'
            user.statut = 'EAQUIPE'
            user.is_staff = True

            # Activer automatiquement tous les utilisateurs EAQUIPE
            if user.statut == 'EAQUIPE':
                user.is_active = True

            # Si tu veux aussi créer un superutilisateur via l'inscription :
            if user.username == 'admin':  # ← Tu peux changer ce critère
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True

            user.save()
            messages.success(request, "Inscription réussie. Vous pouvez maintenant vous connecter.")
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


from django.http import FileResponse, HttpResponse
from .models import DocumentNumerique, DemandeActe
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@login_required
def download_acte(request, demande_id):
    demande = DemandeActe.objects.get(pk=demande_id)
    
    # Vérifier les permissions
    if request.user != demande.demandeur and not request.user.is_staff:
        raise PermissionDenied
    
    # Récupérer ou générer le document
    document = demande.documents.filter(type_document='ACTE').first()
    if not document:
        document = DocumentNumerique.objects.create(
            demande=demande,
            type_document='ACTE'
        )
        document.generate_acte_pdf()
    
    response = FileResponse(document.fichier)
    response['Content-Disposition'] = f'attachment; filename="{document.nom_fichier}"'
    return response

@login_required
def verify_signature(request, document_id):
    document = DocumentNumerique.objects.get(pk=document_id)
    
    # Vérifier les permissions
    if request.user != document.demande.demandeur and not request.user.is_staff:
        raise PermissionDenied
    
    is_valid = document.verify_signature()
    
    return HttpResponse(f"Signature {'valide' if is_valid else 'invalide'}")



from django.http import JsonResponse
from core.models import DemandeActe, Tarif

def get_tarif_from_demande(request, demande_id):
    try:
        demande = DemandeActe.objects.get(pk=demande_id)
        tarif = Tarif.objects.get(type_acte=demande.type_acte, actif=True)
        quantite = demande.nombre_exemplaires  # ou autre champ
        return JsonResponse({
            'success': True,
            'montant': float(tarif.prix_unitaire) * quantite,
            'timbre': float(tarif.timbre_fiscal),
            'total': float(tarif.prix_unitaire + tarif.timbre_fiscal) * quantite,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

@csrf_exempt
@require_POST
def cinetpay_webhook(request):
    """Webhook pour recevoir les confirmations CinetPay"""
    try:
        data = json.loads(request.body)
        
        transaction_id = data.get('cpm_trans_id')
        status = data.get('cpm_result')
        
        # Trouver le paiement
        paiement = Paiement.objects.get(reference_transaction=transaction_id)
        
        if status == '00':  # Succès
            paiement.confirmer()
        else:
            paiement.echec(code_erreur=status, message_erreur=data.get('cpm_error_message', ''))
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



@staff_member_required
def initiate_payment_view(request, demande_id):
    demande = get_object_or_404(DemandeActe, id=demande_id)

    if demande.statut_paiement == 'PAYE':
        messages.warning(request, "Cette demande est déjà payée.")
        return redirect('admin:core_demandeacte_change', demande_id)

    transaction_id = f"ACTE_{demande.id}_{uuid.uuid4().hex[:8]}"
    amount = int(demande.tarif.prix) if demande.tarif else 1000

    paiement = Paiement.objects.create(
        demande_acte=demande,
        montant=amount,
        reference_transaction=transaction_id,
        statut='EN_ATTENTE',
        methode_paiement='CINETPAY'
    )

    service = CinetPayService()
    result = service.initiate_payment(paiement)

    if result.get('success'):
        return redirect(result['payment_url'])
    else:
        messages.error(request, f"Erreur lors de l'initiation du paiement : {result.get('error', 'Erreur inconnue')}")
        return redirect('admin:core_demandeacte_change', demande_id)


@csrf_exempt
def payment_webhook_view(request):
    if request.method == 'POST':
        data = request.POST
        transaction_id = data.get('cpm_trans_id')
        payment_status = data.get('cpm_result')

        try:
            paiement = Paiement.objects.get(reference_transaction=transaction_id)

            if paiement.statut != 'VALIDE' and payment_status == '00':
                paiement.statut = 'VALIDE'
                paiement.save()

                demande = paiement.demande_acte
                demande.statut_paiement = 'PAYE'
                demande.save()

            return JsonResponse({'status': 'success'}, status=200)

        except Paiement.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Paiement introuvable'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)
