from django.urls import path
from empleado import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='empleado_dashboard'),
    path('recepcionar/', views.recepcionar_envio_view, name='empleado_recepcionar'),
    path('estado/', views.actualizar_estado_view, name='empleado_estado'),
    path('incidencia/', views.registrar_incidencia_view, name='empleado_incidencia'),
]