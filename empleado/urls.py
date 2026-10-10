from django.urls import path
from empleado import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='empleado_dashboard'),
    path('recepcionar/', views.recepcionar_envio_view, name='empleado_recepcionar'),
    path('estado/', views.actualizar_estado_view, name='empleado_estado'),
    path('ausente/', views.marcar_ausente_view, name='empleado_ausente'),
    path('recepcionar/danado/', views.recepcionar_danado_view, name='empleado_recepcionar_danado'),
    path('recepcionar/finalizar/', views.finalizar_recepcion_view, name='empleado_finalizar_recepcion'),
    path('reportar-danio/', views.reportar_danio_view, name='empleado_reportar_danio'),
    path('reportar-perdida/', views.reportar_perdida_view, name='empleado_reportar_perdida'),
    path('reparto/', views.preparar_reparto_view, name='empleado_preparar_reparto'),
    path('reparto/despachar/', views.despachar_zona_view, name='empleado_despachar_zona'),
    path('reparto/asignar-zona/', views.asignar_zona_manual_view, name='empleado_asignar_zona'),
    path('reparto/ubicacion/', views.actualizar_ubicacion_view, name='empleado_actualizar_ubicacion'),
]