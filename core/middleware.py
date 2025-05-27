# core/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

class AdminRedirectMiddleware:
    """
    Middleware pour rediriger automatiquement les utilisateurs vers leur tableau de bord approprié
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Traitement avant la vue
        response = self.process_request(request)
        if response:
            return response
            
        response = self.get_response(request)
        return response

    def process_request(self, request):
        """
        Redirige les utilisateurs authentifiés vers leur tableau de bord approprié
        """
        # Ne traiter que les requêtes vers les pages d'admin
        if not request.path.startswith('/admin/') and not request.path.startswith('/dashboard/'):
            return None
            
        # Ignorer si l'utilisateur n'est pas authentifié
        if not request.user.is_authenticated:
            return None
            
        # Ignorer les requêtes AJAX et API
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return None
            
        # Obtenir le rôle de l'utilisateur
        user_role = getattr(request.user, 'role', None)
        
        # Définir les redirections par rôle
        role_redirections = {
            'admin': '/super-admin/',
            'agent': '/agent/',
            'citoyen': '/citoyen/',
        }
        
        # Si l'utilisateur accède à /admin/ ou /dashboard/, le rediriger vers son tableau de bord
        if request.path in ['/admin/', '/dashboard/'] and user_role in role_redirections:
            target_url = role_redirections[user_role]
            logger.info(f"Redirection de l'utilisateur {request.user.username} ({user_role}) vers {target_url}")
            return redirect(target_url)
            
        # Vérifier que l'utilisateur accède au bon tableau de bord
        current_path = request.path
        
        if user_role == 'admin' and not current_path.startswith('/super-admin/'):
            if current_path.startswith(('/agent/', '/citoyen/', '/admin/')):
                return redirect('/super-admin/')
                
        elif user_role == 'agent' and not current_path.startswith('/agent/'):
            if current_path.startswith(('/super-admin/', '/citoyen/', '/admin/')):
                return redirect('/agent/')
                
        elif user_role == 'citoyen' and not current_path.startswith('/citoyen/'):
            if current_path.startswith(('/super-admin/', '/agent/', '/admin/')):
                return redirect('/citoyen/')
        
        return None


class LoginRedirectMiddleware:
    """
    Middleware pour rediriger après connexion vers le bon tableau de bord
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Après une connexion réussie, rediriger vers le bon tableau de bord
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.path == '/admin/login/' and 
            response.status_code == 302):
            
            user_role = getattr(request.user, 'role', None)
            role_redirections = {
                'admin': '/super-admin/',
                'agent': '/agent/',
                'citoyen': '/citoyen/',
            }
            
            if user_role in role_redirections:
                response['Location'] = role_redirections[user_role]
                logger.info(f"Redirection post-connexion pour {request.user.username} vers {role_redirections[user_role]}")
        
        return response