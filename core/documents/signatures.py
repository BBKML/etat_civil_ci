import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from django.conf import settings
import os
import base64

class DigitalSigner:
    @staticmethod
    def generate_file_hash(file_path):
        """Génère un hash SHA-256 du fichier"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def sign_data(data, private_key_path=None):
        """Signe des données avec une clé privée"""
        if private_key_path is None:
            private_key_path = os.path.join(settings.BASE_DIR, 'keys/private_key.pem')
        
        with open(private_key_path, 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
        
        signature = private_key.sign(
            data.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def verify_signature(data, signature, public_key_path=None):
        """Vérifie une signature avec une clé publique"""
        if public_key_path is None:
            public_key_path = os.path.join(settings.BASE_DIR, 'keys/public_key.pem')
        
        with open(public_key_path, 'rb') as key_file:
            public_key = load_pem_public_key(
                key_file.read(),
                backend=default_backend()
            )
        
        try:
            public_key.verify(
                base64.b64decode(signature),
                data.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    @staticmethod
    def sign_document(document_path, private_key_path=None):
        """Signe un document et retourne la signature"""
        file_hash = DigitalSigner.generate_file_hash(document_path)
        return DigitalSigner.sign_data(file_hash, private_key_path)