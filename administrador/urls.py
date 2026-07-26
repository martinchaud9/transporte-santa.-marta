from django.urls import path
from administrador import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='admin_dashboard'),
    path('empleados/nuevo/', views.registro_empleado_view, name='registro_empleado'),
    path('vehiculos/nuevo/', views.registro_vehiculo_view, name='registro_vehiculo'),
    path('reportes/', views.generar_reporte_view, name='generar_reporte'),
    path('pagos/nuevo/', views.registrar_pago_view, name='registrar_pago'),
    path('pagos/<int:pago_id>/editar/', views.editar_pago_view, name='editar_pago'),
    path('pagos/<int:pago_id>/anular/', views.anular_pago_view, name='anular_pago'),
]