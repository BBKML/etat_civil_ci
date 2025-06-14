from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from core.admin import custom_admin_index, get_dashboard_data, dashboard_data_view
from django.views.generic import TemplateView
from core.views import HelpGuideView, TarifsView, ContactView, process_payment_view, download_acte_view, duplicate_demande_view
from core import views
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core.views import cinetpay_webhook

def redirect_to_home(request):
    return redirect('/')
admin.site.index = custom_admin_index
urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('core.urls')), 
    path('', include('django.contrib.auth.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='admin/login.html'), name='login'),
    path('accounts/profile/', redirect_to_home),
    path('cinetpay/webhook/', cinetpay_webhook, name='cinetpay_webhook'),
    
    path('api/payment/webhook/cinetpay/', views.cinetpay_webhook, name='cinetpay_webhook'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/dashboard-data/', dashboard_data_view, name='dashboard_data'),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('help-guide/', HelpGuideView.as_view(), name='help_guide'),
    path('tarifs/', TarifsView.as_view(), name='tarifs'),
    path('contact/', ContactView.as_view(), name='contact'),
    path('paiement/<int:demande_id>/',  process_payment_view,  name='process_payment'),
    path('telecharger/<int:demande_id>/', download_acte_view,  name='download_acte'),
    path('dupliquer/<int:demande_id>/', duplicate_demande_view, name='duplicate_demande'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)