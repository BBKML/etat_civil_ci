from django.urls import path
from . import views
from .views import register_view
app_name='core'
urlpatterns = [
    path('', views.home, name='home'),
    path('admin/change-status/<int:demande_id>/<str:status>/', views.change_demande_status, name='change_demande_status'),
    path('admin/statistiques/', views.statistiques_view, name='admin_statistiques'),
    path("register/", register_view, name="register"),
    path('admin/rapports/', views.rapports_view, name='admin_rapports'),
    path('admin/demandes-aujourd-hui/', views.demandes_aujourd_hui_view, name='demandes_aujourd_hui'),
    path('admin/demande/<int:pk>/approuver/', views.approuver_demande, name='approuver_demande'),
    path('admin/demande/<int:pk>/rejeter/', views.rejeter_demande, name='rejeter_demande'),
    path('admin/demande/<int:pk>/delivrer/', views.delivrer_demande, name='delivrer_demande'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    
]