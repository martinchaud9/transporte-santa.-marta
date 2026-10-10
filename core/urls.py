from django.urls import path
from core import views

urlpatterns = [
    path('', views.inicio_view, name='inicio'),
    path('registro/', views.registro_cliente_view, name='registro_cliente'),
    path('rastrear/', views.rastrear_envio_view, name='rastrear_envio'),
    path('rastrear/ubicacion/<str:codigo>/', views.ubicacion_envio_view, name='ubicacion_envio'),
    path('logout/', views.logout_view, name='logout'),
]