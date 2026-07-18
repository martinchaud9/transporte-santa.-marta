from django.urls import path
from administrador import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='admin_dashboard'),
    path('empleados/nuevo/', views.registro_empleado_view, name='registro_empleado'),
]