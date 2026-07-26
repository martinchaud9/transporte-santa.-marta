from datetime import datetime, timedelta

from django.db.models import Sum
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Usuario, Envio, Vehiculo, Incidencia, Pago, Reclamo
from core.forms import RegistroEmpleadoForm, RegistroVehiculoForm, PagoForm

MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]

def _contexto_dashboard():
    anio_actual = timezone.now().year
    return {
        'empleados': Usuario.objects.filter(rol='empleado'),
        'clientes': Usuario.objects.filter(rol='cliente'),
        'envios': Envio.objects.exclude(estado='entregado').order_by('-fecha_registro'),
        'envios_entregados': Envio.objects.filter(estado='entregado').order_by('-fecha_registro'),
        'vehiculos': Vehiculo.objects.select_related('empleado').all(),
        'meses': MESES,
        'anios_disponibles': range(anio_actual - 2, anio_actual + 1),
        'pagos': Pago.objects.select_related('envio', 'envio__destinatario').order_by('-fecha'),
        'envios_sin_pago': Envio.objects.filter(pagos__isnull=True).select_related('destinatario'),
        'todos_los_envios': Envio.objects.select_related('destinatario').order_by('-fecha_registro'),
    }

@login_required
def dashboard_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    contexto = _contexto_dashboard()

    ahora = timezone.now()
    hoy = ahora.date()
    hace_semana = ahora - timedelta(days=7)

    eventos = []
    for envio in Envio.objects.filter(estado='entregado').order_by('-fecha_actualizacion')[:5]:
        eventos.append({'texto': f'{envio.codigo} marcado como Entregado', 'fecha': envio.fecha_actualizacion, 'color': 'dot-green'})
    for pago in Pago.objects.select_related('envio').order_by('-fecha')[:5]:
        eventos.append({'texto': f'Pago registrado para {pago.envio.codigo}', 'fecha': pago.fecha, 'color': 'dot-blue'})
    for inc in Incidencia.objects.select_related('envio').order_by('-fecha')[:5]:
        eventos.append({'texto': f'Incidencia en {inc.envio.codigo}: {inc.get_tipo_display()}', 'fecha': inc.fecha, 'color': 'dot-orange'})
    eventos.sort(key=lambda e: e['fecha'], reverse=True)

    contexto.update({
        'envios_hoy': Envio.objects.filter(fecha_registro__date=hoy).count(),
        'entregas_hoy': Envio.objects.filter(estado='entregado', fecha_actualizacion__date=hoy).count(),
        'pendientes_total': contexto['envios'].count(),
        'pagos_semana': Pago.objects.filter(fecha__gte=hace_semana).aggregate(total=Sum('monto'))['total'] or 0,
        'envios_recientes': Envio.objects.select_related('destinatario').order_by('-fecha_actualizacion')[:5],
        'actividad_reciente': eventos[:5],
        'reclamos_pendientes': Reclamo.objects.select_related('envio').exclude(estado='resuelto').order_by('-fecha_creacion')[:5],
    })
    return render(request, 'administrador/dashboard.html', contexto)

@login_required
def registro_empleado_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = RegistroEmpleadoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
        else:
            print(form.errors)
    return redirect('admin_dashboard')

@login_required
def registro_vehiculo_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = RegistroVehiculoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
        else:
            print(form.errors)
    return redirect('admin_dashboard')

@login_required
def generar_reporte_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    tipo = request.GET.get('tipo', 'semanal')
    anio = request.GET.get('anio', '')
    mes = request.GET.get('mes', '')
    ahora = timezone.now()

    if tipo == 'mensual' and anio and mes:
        anio, mes = int(anio), int(mes)
        inicio = timezone.make_aware(datetime(anio, mes, 1))
        if mes == 12:
            fin = timezone.make_aware(datetime(anio + 1, 1, 1))
        else:
            fin = timezone.make_aware(datetime(anio, mes + 1, 1))
    else:
        tipo = 'semanal'
        anio, mes = ahora.year, ahora.month
        inicio = ahora - timedelta(days=7)
        fin = ahora

    umbral_demora = ahora - timedelta(days=Envio.UMBRAL_DEMORA_DIAS)
    reporte = {
        'tipo': tipo,
        'anio': anio,
        'mes': mes,
        'mes_nombre': dict(MESES).get(mes, ''),
        'inicio': inicio,
        'fin': fin,
        'envios_registrados': Envio.objects.filter(fecha_registro__range=(inicio, fin)).count(),
        'envios_entregados': Envio.objects.filter(estado='entregado', fecha_actualizacion__range=(inicio, fin)).count(),
        'incidencias': Incidencia.objects.filter(fecha__range=(inicio, fin)).count(),
        'demorados_actuales': Envio.objects.filter(estado__in=Envio.ESTADOS_ACTIVOS, fecha_actualizacion__lt=umbral_demora).count(),
    }

    contexto = _contexto_dashboard()
    contexto.update({'reporte': reporte, 'mostrar_reportes': True})
    return render(request, 'administrador/dashboard.html', contexto)

@login_required
def registrar_pago_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = PagoForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.registrado_por = request.user
            pago.save()
            return redirect('admin_dashboard')
        else:
            print(form.errors)
    return redirect('admin_dashboard')

@login_required
def editar_pago_view(request, pago_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        pago = Pago.objects.get(id=pago_id)
    except Pago.DoesNotExist:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
        else:
            print(form.errors)
            return redirect('admin_dashboard')

    contexto = _contexto_dashboard()
    contexto.update({'pago_editar': pago, 'mostrar_editar_pago': True})
    return render(request, 'administrador/dashboard.html', contexto)

@login_required
def anular_pago_view(request, pago_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            pago = Pago.objects.get(id=pago_id)
            if pago.envio.estado != 'entregado':
                pago.anulado = True
                pago.save()
        except Pago.DoesNotExist:
            pass
    return redirect('admin_dashboard')