from django.urls import path
from cliente import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='cliente_dashboard'),
    path('reclamo/', views.generar_reclamo_view, name='cliente_reclamo'),
    path('pagar/', views.pagar_envio_view, name='cliente_pagar'),
    path('modificar-datos/', views.modificar_datos_view, name='cliente_modificar_datos'),
]