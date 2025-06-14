import json
import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from .models import Paiement
from .services.payment_service import CinetPayService

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def payment_notify(request):
    """
    Webhook de notification CinetPay
    Cette URL sera appelée par CinetPay pour notifier du statut du paiement
    """
    try:
        # Récupération des données de la notification
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST.dict()
        
        logger.info(f"Notification CinetPay reçue: {data}")
        
        # Récupération des paramètres importants
        transaction_id = data.get('cpm_trans_id') or data.get('transaction_id')
        payment_token = data.get('cpm_token') or data.get('payment_token')
        status = data.get('cpm_result') or data.get('status')
        
        if not transaction_id:
            logger.error("Transaction ID manquant dans la notification")
            return HttpResponse("Transaction ID requis", status=400)
        
        # Recherche du paiement
        try:
            paiement = Paiement.objects.get(reference_transaction=transaction_id)
        except Paiement.DoesNotExist:
            logger.error(f"Paiement non trouvé pour transaction_id: {transaction_id}")
            return HttpResponse("Paiement non trouvé", status=404)
        
        # Vérification du paiement via l'API CinetPay
        cinetpay_service = CinetPayService()
        verification_result = cinetpay_service.verify_payment_by_transaction_id(transaction_id)
        
        if verification_result['success']:
            new_status = verification_result['status']
            
            # Mise à jour du statut selon la vérification
            if new_status == 'CONFIRME' and paiement.statut != 'CONFIRME':
                paiement.confirmer()
                logger.info(f"Paiement {transaction_id} confirmé via notification")
                
            elif new_status == 'ECHEC' and paiement.statut not in ['ECHEC', 'EXPIRE', 'ANNULE']:
                paiement.echec(
                    code_erreur='CINETPAY_REJECT',
                    message_erreur='Paiement rejeté par CinetPay'
                )
                logger.info(f"Paiement {transaction_id} marqué comme échoué")
                
            elif new_status in ['ANNULE', 'EXPIRE']:
                paiement.statut = new_status
                paiement.save(update_fields=['statut'])
                logger.info(f"Paiement {transaction_id} mis à jour: {new_status}")
        else:
            logger.error(f"Erreur lors de la vérification: {verification_result['error']}")
        
        # Réponse de succès à CinetPay
        return HttpResponse("OK", status=200)
        
    except Exception as e:
        logger.error(f"Erreur dans payment_notify: {str(e)}")
        return HttpResponse("Erreur serveur", status=500)


@require_GET
def payment_return(request):
    """
    Page de retour après paiement
    L'utilisateur est redirigé ici après avoir effectué le paiement
    """
    try:
        # Récupération des paramètres de retour
        transaction_id = request.GET.get('transaction_id')
        token = request.GET.get('token')
        status = request.GET.get('status')
        
        logger.info(f"Retour de paiement - Transaction: {transaction_id}, Token: {token}, Status: {status}")
        
        context = {
            'transaction_id': transaction_id,
            'token': token,
            'status': status,
            'paiement': None,
            'verification_result': None
        }
        
        if transaction_id:
            try:
                paiement = Paiement.objects.get(reference_transaction=transaction_id)
                context['paiement'] = paiement
                
                # Vérification du statut via l'API
                cinetpay_service = CinetPayService()
                verification_result = cinetpay_service.verify_payment_by_transaction_id(transaction_id)
                context['verification_result'] = verification_result
                
                if verification_result['success']:
                    # Mise à jour du statut si nécessaire
                    if verification_result['status'] == 'CONFIRME' and paiement.statut != 'CONFIRME':
                        paiement.confirmer()
                        messages.success(request, "Votre paiement a été confirmé avec succès!")
                    elif verification_result['status'] == 'ECHEC':
                        messages.error(request, "Votre paiement a échoué. Veuillez réessayer.")
                    elif verification_result['status'] == 'EN_COURS':
                        messages.info(request, "Votre paiement est en cours de traitement.")
                else:
                    messages.warning(request, "Impossible de vérifier le statut de votre paiement.")
                    
            except Paiement.DoesNotExist:
                messages.error(request, "Transaction non trouvée.")
        
        return render(request, 'admin/payment_return.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dans payment_return: {str(e)}")
        messages.error(request, "Une erreur est survenue lors du traitement de votre retour.")
        return render(request, 'admin/payment_return.html', {'error': str(e)})


@staff_member_required
def payment_interface(request, object_id):
    """
    Interface de paiement pour l'admin
    """
    paiement = get_object_or_404(Paiement, pk=object_id)
    
    if request.method == 'POST':
        # Traitement du formulaire de paiement
        methode = request.POST.get('methode_paiement')
        numero_telephone = request.POST.get('numero_telephone', '')
        
        # Mise à jour du paiement
        paiement.methode_paiement = methode
        if numero_telephone:
            paiement.numero_telephone = numero_telephone
        
        paiement.save(update_fields=['methode_paiement', 'numero_telephone'])
        
        # Initiation du paiement
        try:
            cinetpay_service = CinetPayService()
            result = cinetpay_service.initiate_payment(paiement)
            
            if result['success']:
                messages.success(request, "Paiement initié avec succès!")
                if 'payment_url' in result:
                    return redirect(result['payment_url'])
            else:
                messages.error(request, f"Erreur: {result['error']}")
                
        except Exception as e:
            messages.error(request, f"Erreur technique: {str(e)}")
    
    context = {
        'paiement': paiement,
        'methodes_paiement': Paiement.METHODE_PAIEMENT_CHOICES,
        'title': f'Interface de paiement - {paiement.reference_transaction}'
    }
    
    return render(request, 'admin/payment_interface.html', context)


@method_decorator(staff_member_required, name='dispatch')
class PaymentStatusView(View):
    """
    Vue AJAX pour vérifier le statut d'un paiement
    """
    
    def get(self, request, object_id):
        try:
            paiement = get_object_or_404(Paiement, pk=object_id)
            
            # Vérification via CinetPay
            cinetpay_service = CinetPayService()
            result = cinetpay_service.verify_payment_by_transaction_id(paiement.reference_transaction)
            
            if result['success']:
                # Mise à jour du statut local si nécessaire
                if result['status'] != paiement.statut:
                    old_status = paiement.statut
                    
                    if result['status'] == 'CONFIRME':
                        paiement.confirmer()
                    elif result['status'] == 'ECHEC':
                        paiement.echec('CINETPAY_API', 'Paiement rejeté par CinetPay')
                    else:
                        paiement.statut = result['status']
                        paiement.save(update_fields=['statut'])
                    
                    logger.info(f"Statut paiement {paiement.reference_transaction} mis à jour: {old_status} -> {result['status']}")
                
                return JsonResponse({
                    'success': True,
                    'status': paiement.statut,
                    'status_display': paiement.get_statut_display(),
                    'amount': float(result.get('amount', 0)),
                    'payment_method': result.get('payment_method', ''),
                    'updated': True
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error'],
                    'status': paiement.statut,
                    'status_display': paiement.get_statut_display()
                })
                
        except Exception as e:
            logger.error(f"Erreur dans PaymentStatusView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


# Vue pour les statistiques de paiement (bonus)
@staff_member_required
def payment_stats(request):
    """
    Statistiques des paiements
    """
    from django.db.models import Count, Sum, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Statistiques générales
    stats = {
        'total_paiements': Paiement.objects.count(),
        'paiements_confirmes': Paiement.objects.filter(statut='CONFIRME').count(),
        'montant_total': Paiement.objects.filter(statut='CONFIRME').aggregate(
            total=Sum('montant_total')
        )['total'] or 0,
        'paiements_en_attente': Paiement.objects.filter(statut='EN_ATTENTE').count(),
        'paiements_echec': Paiement.objects.filter(statut='ECHEC').count(),
    }
    
    # Statistiques par méthode de paiement
    stats['par_methode'] = Paiement.objects.values('methode_paiement').annotate(
        count=Count('id'),
        montant=Sum('montant_total')
    ).order_by('-count')
    
    # Statistiques des 7 derniers jours
    week_ago = timezone.now() - timedelta(days=7)
    stats['cette_semaine'] = Paiement.objects.filter(
        date_paiement__gte=week_ago
    ).values('date_paiement__date').annotate(
        count=Count('id'),
        montant=Sum('montant_total')
    ).order_by('date_paiement__date')
    
    return render(request, 'admin/payment_stats.html', {'stats': stats})