from django.urls import path
from administrador import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='admin_dashboard'),
    path('empleados/nuevo/', views.registro_empleado_view, name='registro_empleado'),
    path('empleados/<int:empleado_id>/eliminar/', views.eliminar_empleado_view, name='eliminar_empleado'),
    path('vehiculos/nuevo/', views.registro_vehiculo_view, name='registro_vehiculo'),
    path('reportes/', views.generar_reporte_view, name='generar_reporte'),
    path('reportes/pdf/', views.generar_reporte_pdf_view, name='generar_reporte_pdf'),
    path('vehiculos/<int:vehiculo_id>/editar/', views.editar_vehiculo_view, name='editar_vehiculo'),
    path('vehiculos/<int:vehiculo_id>/eliminar/', views.eliminar_vehiculo_view, name='eliminar_vehiculo'),
    path('envios/<int:envio_id>/', views.detalle_envio_view, name='detalle_envio'),
    path('reclamos/<int:reclamo_id>/gestionar/', views.gestionar_reclamo_view, name='gestionar_reclamo'),
    path('pagos/<int:pago_id>/anular/', views.anular_pago_view, name='anular_pago'),
]