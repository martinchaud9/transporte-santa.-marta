from django.urls import path
from cliente import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='cliente_dashboard'),
    path('reclamo/', views.generar_reclamo_view, name='cliente_reclamo'),
]