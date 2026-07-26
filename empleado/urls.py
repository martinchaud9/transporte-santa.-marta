from django.urls import path
from empleado import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='empleado_dashboard'),
    path('recepcionar/', views.recepcionar_envio_view, name='empleado_recepcionar'),
    path('estado/', views.actualizar_estado_view, name='empleado_estado'),
    path('incidencia/', views.registrar_incidencia_view, name='empleado_incidencia'),
    path('reparto/', views.preparar_reparto_view, name='empleado_preparar_reparto'),
    path('reparto/despachar/', views.despachar_zona_view, name='empleado_despachar_zona'),
    path('reparto/asignar-zona/', views.asignar_zona_manual_view, name='empleado_asignar_zona'),
]