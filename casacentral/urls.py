from django.urls import path
from casacentral import views

urlpatterns = [
    path('', views.dashboard_view, name='casacentral_dashboard'),
    path('envios/nuevo/', views.nuevo_envio_view, name='casacentral_nuevo_envio'),
    path('clientes/buscar/', views.buscar_cliente_view, name='casacentral_buscar_cliente'),
    path('despachar/', views.despachar_camion_view, name='casacentral_despachar'),
    path('qr/<str:codigo>/', views.qr_envio_view, name='casacentral_qr_envio'),
]