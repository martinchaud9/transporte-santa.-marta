from datetime import datetime, timedelta

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Usuario, Envio, Vehiculo, Incidencia, Pago, Reclamo, Despacho, LogAuditoria
from core.forms import RegistroEmpleadoForm, RegistroVehiculoForm, EditarVehiculoForm

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
        'despachos': Despacho.objects.prefetch_related('envios__destinatario').order_by('-fecha_salida'),
        'incidencias': Incidencia.objects.select_related('envio', 'envio__destinatario', 'registrado_por').order_by('-fecha'),
        'reclamos': Reclamo.objects.select_related('envio', 'cliente').order_by('-fecha_creacion'),
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
            messages.success(request, '✓ Empleado registrado correctamente.')
            return redirect('admin_dashboard')

        if 'dni' in form.errors:
            error_empleado = form.errors['dni'][0]
        else:
            error_empleado = 'Revisá los datos ingresados: hay errores en el formulario.'
        contexto = _contexto_dashboard()
        contexto.update({
            'error_empleado': error_empleado,
            'datos_empleado': request.POST,
            'mostrar_nuevo_empleado': True,
        })
        return render(request, 'administrador/dashboard.html', contexto)
    return redirect('admin_dashboard')

@login_required
def eliminar_empleado_view(request, empleado_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            empleado = Usuario.objects.get(id=empleado_id, rol='empleado')
        except Usuario.DoesNotExist:
            return redirect('admin_dashboard')

        # Baja lógica: no se borra el registro para conservar el historial de
        # operaciones (envíos recepcionados, incidencias, etc.); solo se
        # deshabilita la cuenta, lo que revoca el acceso al sistema.
        empleado.is_active = False
        empleado.save(update_fields=['is_active'])
        LogAuditoria.objects.create(
            accion='baja_empleado',
            usuario_afectado=empleado,
            realizado_por=request.user,
            detalle=f'Cuenta deshabilitada por {request.user.get_full_name() or request.user.username}.',
        )
        messages.success(request, f'✓ Se deshabilitó el acceso de {empleado.get_full_name() or empleado.username}. Su historial se conserva.')
    return redirect('admin_dashboard')

@login_required
def registro_vehiculo_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = RegistroVehiculoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✓ Vehículo registrado correctamente.')
            return redirect('admin_dashboard')

        if 'patente' in form.errors:
            error_vehiculo = form.errors['patente'][0]
        elif 'empleado' in form.errors:
            error_vehiculo = form.errors['empleado'][0]
        else:
            error_vehiculo = 'Revisá los datos ingresados: hay errores en el formulario.'
        contexto = _contexto_dashboard()
        contexto.update({
            'error_vehiculo': error_vehiculo,
            'datos_vehiculo': request.POST,
            'mostrar_nuevo_vehiculo': True,
        })
        return render(request, 'administrador/dashboard.html', contexto)
    return redirect('admin_dashboard')

def _calcular_reporte(request):
    """Calcula las métricas del reporte a partir de los parámetros GET
    (tipo/anio/mes). Se usa tanto para mostrarlo en pantalla como para el PDF,
    así ambos siempre muestran exactamente los mismos números."""
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
    return {
        'tipo': tipo,
        'anio': anio,
        'mes': mes,
        'mes_nombre': dict(MESES).get(mes, ''),
        'inicio': inicio,
        'fin': fin,
        'generado': ahora,
        'envios_registrados': Envio.objects.filter(fecha_registro__range=(inicio, fin)).count(),
        'envios_entregados': Envio.objects.filter(estado='entregado', fecha_actualizacion__range=(inicio, fin)).count(),
        'incidencias': Incidencia.objects.filter(fecha__range=(inicio, fin)).count(),
        'demorados_actuales': Envio.objects.filter(estado__in=Envio.ESTADOS_ACTIVOS, fecha_actualizacion__lt=umbral_demora).count(),
    }


@login_required
def generar_reporte_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    reporte = _calcular_reporte(request)
    contexto = _contexto_dashboard()
    contexto.update({'reporte': reporte, 'mostrar_reportes': True})
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def generar_reporte_pdf_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    reporte = _calcular_reporte(request)

    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = []

    if reporte['tipo'] == 'mensual':
        periodo_texto = f"Mensual — {reporte['mes_nombre']} {reporte['anio']}"
    else:
        periodo_texto = f"Semanal — del {reporte['inicio']:%d/%m/%Y} al {reporte['fin']:%d/%m/%Y}"

    elementos.append(Paragraph('Transporte Santa Marta', estilos['Title']))
    elementos.append(Paragraph('Reporte de operaciones — Sucursal Santiago del Estero', estilos['Heading2']))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph(f"<b>Período del reporte:</b> {periodo_texto}", estilos['Normal']))
    elementos.append(Paragraph(f"<b>Fecha de generación:</b> {reporte['generado']:%d/%m/%Y %H:%M} hs", estilos['Normal']))
    elementos.append(Spacer(1, 0.8 * cm))

    filas = [
        ['Métrica', 'Valor'],
        ['Envíos registrados en el período', str(reporte['envios_registrados'])],
        ['Envíos entregados en el período', str(reporte['envios_entregados'])],
        ['Incidencias registradas en el período', str(reporte['incidencias'])],
        ['Envíos demorados en este momento', str(reporte['demorados_actuales'])],
    ]
    tabla = Table(filas, colWidths=[11 * cm, 5 * cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a2240')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e3edf8')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f6ff')]),
    ]))
    elementos.append(tabla)

    doc.build(elementos)
    buffer.seek(0)

    nombre_archivo = f"reporte_{reporte['tipo']}_{reporte['generado']:%Y-%m-%d}.pdf"
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

@login_required
def editar_vehiculo_view(request, vehiculo_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        vehiculo = Vehiculo.objects.get(id=vehiculo_id)
    except Vehiculo.DoesNotExist:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = EditarVehiculoForm(request.POST, instance=vehiculo)
        if form.is_valid():
            form.save()
            messages.success(request, '✓ Vehículo actualizado correctamente.')
            return redirect('admin_dashboard')

        if 'empleado' in form.errors:
            error_vehiculo = form.errors['empleado'][0]
        else:
            error_vehiculo = 'Revisá los datos ingresados: hay errores en el formulario.'
        contexto = _contexto_dashboard()
        contexto.update({
            'vehiculo_editar': vehiculo,
            'error_vehiculo_editar': error_vehiculo,
            'datos_vehiculo_editar': request.POST,
            'mostrar_editar_vehiculo': True,
        })
        return render(request, 'administrador/dashboard.html', contexto)

    contexto = _contexto_dashboard()
    contexto.update({'vehiculo_editar': vehiculo, 'mostrar_editar_vehiculo': True})
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def eliminar_vehiculo_view(request, vehiculo_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            vehiculo = Vehiculo.objects.get(id=vehiculo_id)
            vehiculo.delete()
        except Vehiculo.DoesNotExist:
            pass
    return redirect('admin_dashboard')


@login_required
def detalle_envio_view(request, envio_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        envio = Envio.objects.select_related('destinatario').get(id=envio_id)
    except Envio.DoesNotExist:
        return redirect('admin_dashboard')

    contexto = _contexto_dashboard()
    contexto.update({
        'envio_detalle': envio,
        'envio_pagos': envio.pagos.filter(anulado=False),
        'envio_incidencias': envio.incidencias.all(),
        'mostrar_detalle_envio': True,
    })
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def gestionar_reclamo_view(request, reclamo_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        reclamo = Reclamo.objects.select_related('envio', 'cliente').get(id=reclamo_id)
    except Reclamo.DoesNotExist:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        estado = request.POST.get('estado')
        respuesta = request.POST.get('respuesta', '')
        if estado in dict(Reclamo.ESTADO_CHOICES):
            reclamo.estado = estado
            reclamo.respuesta = respuesta
            reclamo.save()
        return redirect('admin_dashboard')

    contexto = _contexto_dashboard()
    contexto.update({'reclamo_gestionar': reclamo, 'mostrar_gestionar_reclamo': True})
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