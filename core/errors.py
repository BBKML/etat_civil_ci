from django.http import JsonResponse

class APIError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status

def handle_api_error(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except APIError as e:
            return JsonResponse({'error': e.message}, status=e.status)
        except Exception as e:
            return JsonResponse({'error': 'Erreur serveur'}, status=500)
    return wrapper