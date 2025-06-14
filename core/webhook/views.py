# 1. Créer un service CinetPay - core/services/cinetpay_service.py
import requests
import json
from django.conf import settings
from django.urls import reverse

class CinetPayService:
    def __init__(self):
        self.api_key = settings.CINETPAY_API_KEY
        self.site_id = settings.CINETPAY_SITE_ID
        self.base_url = "https://api-checkout.cinetpay.com/v2/"
    
    def initiate_payment(self, amount, transaction_id, customer_name, customer_email, description="Paiement acte"):
        """Initier un paiement CinetPay"""
        data = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": "XOF",
            "description": description,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "notify_url": f"{settings.BASE_URL}cinetpay/webhook/",
            "return_url": f"{settings.BASE_URL}admin/core/paiement/",
            "cancel_url": f"{settings.BASE_URL}admin/core/paiement/",
        }
        
        response = requests.post(f"{self.base_url}payment", json=data)
        return response.json()
    
    def check_payment_status(self, transaction_id):
        """Vérifier le statut d'un paiement"""
        data = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": transaction_id
        }
        
        response = requests.post(f"{self.base_url}payment/check", json=data)
        return response.json()