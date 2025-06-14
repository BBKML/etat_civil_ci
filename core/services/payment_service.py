import logging
from urllib.parse import urljoin
from django.urls import reverse



logger = logging.getLogger(__name__)

class CinetPayService:
    def __init__(self):
        self.api_key = CINETPAY_API_KEY
        self.site_id = CINETPAY_SITE_ID
        self.cinetpay = CinetPay(api_key=self.api_key, site_id=self.site_id)

    def initiate_payment(self, paiement):
        try:
            notify_url = 'https://votre-domaine.com/paiement/webhook/'  # Assure-toi que ce lien est public (ngrok ou déploiement)
            return_url = urljoin('https://votre-domaine.com/', reverse('admin:core_demandeacte_change', args=[paiement.demande_acte.pk]))

            self.cinetpay.setTransId(paiement.reference_transaction)
            self.cinetpay.setDesignation(f"Paiement pour acte #{paiement.demande_acte.pk}")
            self.cinetpay.setAmount(int(paiement.montant))
            self.cinetpay.setCurrency("XOF")
            self.cinetpay.setLang("fr")
            self.cinetpay.setDebug(True)
            self.cinetpay.setNotifyUrl(notify_url)
            self.cinetpay.setReturnUrl(return_url)

            response = self.cinetpay.getPayUrl()

            if 'code' in response and response['code'] == '201':
                return {
                    'success': True,
                    'payment_url': response['data']['payment_url']
                }
            else:
                logger.error("Erreur CinetPay: %s", response)
                return {'success': False, 'error': response.get('message', 'Erreur inconnue')}
        except Exception as e:
            logger.exception("Erreur lors de l'initiation du paiement CinetPay")
            return {'success': False, 'error': str(e)}
