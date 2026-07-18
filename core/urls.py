from django.urls import path
from core import views

urlpatterns = [
    path('', views.inicio_view, name='inicio'),
    path('registro/', views.registro_cliente_view, name='registro_cliente'),
    path('logout/', views.logout_view, name='logout'),
]