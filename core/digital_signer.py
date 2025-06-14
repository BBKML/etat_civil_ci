import os
import rsa
import base64
from hashlib import sha256
from django.conf import settings

class DigitalSigner:
    @staticmethod
    def generate_keys():
        """Génère une paire de clés RSA et les sauvegarde"""
        try:
            (pubkey, privkey) = rsa.newkeys(2048)
            
            # Créer le répertoire keys s'il n'existe pas
            keys_dir = os.path.join(settings.BASE_DIR, 'keys')
            if not os.path.exists(keys_dir):
                os.makedirs(keys_dir)
            
            # Sauvegarder les clés
            with open(os.path.join(keys_dir, 'public.pem'), 'wb') as f:
                f.write(pubkey.save_pkcs1())
            
            with open(os.path.join(keys_dir, 'private.pem'), 'wb') as f:
                f.write(privkey.save_pkcs1())
            
            return pubkey, privkey
        except Exception as e:
            raise Exception(f"Erreur lors de la génération des clés: {str(e)}")

    @staticmethod
    def load_keys():
        """Charge les clés depuis les fichiers"""
        keys_dir = os.path.join(settings.BASE_DIR, 'keys')
        
        try:
            with open(os.path.join(keys_dir, 'public.pem'), 'rb') as f:
                pubkey = rsa.PublicKey.load_pkcs1(f.read())
            
            with open(os.path.join(keys_dir, 'private.pem'), 'rb') as f:
                privkey = rsa.PrivateKey.load_pkcs1(f.read())
            
            return pubkey, privkey
        except FileNotFoundError:
            # Génère automatiquement les clés si elles n'existent pas
            return DigitalSigner.generate_keys()
        except Exception as e:
            raise Exception(f"Erreur lors du chargement des clés: {str(e)}")

    @staticmethod
    def generate_file_hash(file_path):
        """Génère un hash SHA-256 du fichier"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Le fichier {file_path} n'existe pas")
        
        try:
            sha256_hash = sha256()
            with open(file_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.digest()
        except Exception as e:
            raise Exception(f"Erreur lors du calcul du hash: {str(e)}")

    @staticmethod
    def sign_document(file_path):
        """Signe un document et retourne la signature encodée en base64"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Le fichier {file_path} n'existe pas")
            
            _, privkey = DigitalSigner.load_keys()
            file_hash = DigitalSigner.generate_file_hash(file_path)
            signature = rsa.sign(file_hash, privkey, 'SHA-256')
            return base64.b64encode(signature).decode('utf-8')
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise Exception(f"Erreur lors de la signature du document: {str(e)}")

    @staticmethod
    def verify_signature(file_path, signature_b64):
        """Vérifie la signature d'un document à partir du chemin du fichier"""
        try:
            # 🛠️ Correction ici
            if isinstance(file_path, bytes):
                file_path = file_path.decode('utf-8', errors='ignore')

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Le fichier {file_path} n'existe pas")
            
            if not signature_b64 or not signature_b64.strip():
                return False
            
            pubkey, _ = DigitalSigner.load_keys()
            
            # Recalculer le hash du fichier
            file_hash = DigitalSigner.generate_file_hash(file_path)
            
            # Décoder la signature base64
            signature = base64.b64decode(signature_b64.encode('utf-8'))
            
            # Vérifier la signature
            rsa.verify(file_hash, signature, pubkey)
            return True
            
        except FileNotFoundError as e:
            raise e
        except (rsa.VerificationError, ValueError, base64.binascii.Error):
            return False
        except Exception as e:
            raise Exception(f"Erreur lors de la vérification de la signature: {str(e)}")

    @staticmethod
    def get_signature_info(signature_b64):
        """Retourne des informations sur la signature pour l'affichage"""
        try:
            if not signature_b64 or not signature_b64.strip():
                return {
                    'valid_format': False,
                    'length': 0,
                    'preview': '',
                    'algorithm': 'N/A'
                }
            
            # Vérifier que c'est du base64 valide
            signature_bytes = base64.b64decode(signature_b64.encode('utf-8'))
            
            return {
                'valid_format': True,
                'length': len(signature_bytes),
                'preview': signature_b64[:50] + '...' if len(signature_b64) > 50 else signature_b64,
                'full_signature': signature_b64,
                'algorithm': 'RSA-SHA256',
                'key_size': '2048 bits'
            }
        except Exception:
            return {
                'valid_format': False,
                'length': 0,
                'preview': 'Format invalide',
                'algorithm': 'N/A'
            }