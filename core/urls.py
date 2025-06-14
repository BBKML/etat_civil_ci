from django.urls import path
from . import views
from .views import register_view
from core.views import get_tarif_from_demande
from django.contrib.auth import views as auth_views
from core.views import cinetpay_webhook

app_name='core'
urlpatterns = [
    path('', views.home, name='home'),
    path('admin/change-status/<int:demande_id>/<str:status>/', views.change_demande_status, name='change_demande_status'),
    path('admin/statistiques/', views.statistiques_view, name='admin_statistiques'),
    path('register/', register_view, name='register'),
    path('cinetpay/webhook/', cinetpay_webhook, name='cinetpay_webhook'),

    path('admin/rapports/', views.rapports_view, name='admin_rapports'),
    path('admin/demandes-aujourd-hui/', views.demandes_aujourd_hui_view, name='demandes_aujourd_hui'),
    path('admin/demande/<int:pk>/approuver/', views.approuver_demande, name='approuver_demande'),
    path('admin/demande/<int:pk>/rejeter/', views.rejeter_demande, name='rejeter_demande'),
    path('admin/demande/<int:pk>/delivrer/', views.delivrer_demande, name='delivrer_demande'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/get_tarif_from_demande/<int:demande_id>/', get_tarif_from_demande, name='get_tarif_from_demande'),
    
]