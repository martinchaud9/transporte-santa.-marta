from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Usuario, Envio, Vehiculo, Incidencia, Pago, Reclamo, Despacho, LogAuditoria, SolicitudCancelacion, Consulta
from core.forms import RegistroEmpleadoForm, RegistroVehiculoForm, EditarVehiculoForm, EditarEmpleadoForm
from core.notificaciones import (
    notificar_recibo_pago, notificar_cambio_estado, notificar_reclamo_actualizado,
    notificar_pago_rechazado, notificar_consulta_respondida, notificar_solicitud_cancelacion_rechazada,
)

MENSAJE_SIN_DATOS = 'No hay datos disponibles para el período indicado.'

MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]

def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


def _auditar(request, accion, detalle, **afectados):
    """Deja constancia en la auditoría de una acción del administrador
    (`afectados`: usuario_afectado / pago_afectado / envio_afectado)."""
    LogAuditoria.objects.create(
        accion=accion, realizado_por=request.user, detalle=detalle, **afectados
    )


def _contexto_dashboard():
    # Regla de negocio: un paquete retenido en sucursal más de
    # Envio.UMBRAL_RETENCION_DIAS días sin que el cliente lo retire se
    # devuelve solo a Buenos Aires. Se revisa acá porque es el punto de
    # entrada común a toda vista del panel admin — no hace falta un cron.
    for envio in Envio.devolver_retenidos_vencidos():
        notificar_cambio_estado(envio)

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
        'despachos': Despacho.objects.prefetch_related('envios__destinatario').order_by('-fecha_creacion'),
        'incidencias': Incidencia.objects.select_related('envio', 'envio__destinatario', 'registrado_por').order_by('-fecha'),
        'reclamos': Reclamo.objects.select_related('envio', 'cliente').order_by('-fecha_creacion'),
        'solicitudes_cancelacion_pendientes': SolicitudCancelacion.objects.filter(estado='pendiente').select_related('envio', 'cliente').order_by('fecha_creacion'),
        'solicitudes_cancelacion_resueltas': SolicitudCancelacion.objects.exclude(estado='pendiente').select_related('envio', 'cliente', 'resuelto_por').order_by('-fecha_resolucion')[:15],
        'consultas': Consulta.objects.select_related('cliente').order_by('estado', '-fecha_creacion'),
        'consultas_sin_responder': Consulta.objects.filter(estado='nueva').count(),
        'parametros_sistema': [
            ('Capacidad del camión Buenos Aires → Santiago', f'{Despacho.CAPACIDAD_MAX_PESO_KG} kg',
             'Al superarla, el próximo envío abre un camión nuevo.'),
            ('Capacidad del furgón de reparto por zona', f'{Vehiculo.CAPACIDAD_MAX_PESO_KG} kg',
             'Lo que no entra espera a la próxima salida de la zona.'),
            ('Intentos de entrega por envío', str(Envio.MAX_INTENTOS_ENTREGA),
             'Tras el último intento fallido, el envío queda retenido en la sucursal.'),
            ('Retención en sucursal', f'{Envio.UMBRAL_RETENCION_DIAS} días',
             'Pasado ese plazo, el envío se devuelve solo a Buenos Aires.'),
            ('Alerta de envío demorado', f'más de {Envio.UMBRAL_DEMORA_DIAS} días sin cambios',
             'El envío se marca como “Demorado” en los paneles.'),
            ('Alerta de reclamo demorado', f'más de {Reclamo.UMBRAL_DEMORA_DIAS} días sin respuesta',
             'El reclamo se marca como “Demorado” hasta que se gestione.'),
            ('Zonas de reparto', ', '.join(etiqueta for _, etiqueta in Envio.ZONA_CHOICES),
             'Se asignan según la dirección de entrega de cada envío.'),
        ],
        'mail_activo': 'smtp' in settings.EMAIL_BACKEND,
        'mail_remitente': settings.DEFAULT_FROM_EMAIL,
        'logs_auditoria': LogAuditoria.objects.select_related(
            'realizado_por', 'usuario_afectado', 'pago_afectado', 'pago_afectado__envio', 'envio_afectado'
        ),
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
            empleado = form.save()
            _auditar(
                request, 'alta_empleado',
                f'Alta del empleado {_nombre(empleado)} (usuario {empleado.username}, DNI {empleado.dni}) '
                f'por {_nombre(request.user)}.',
                usuario_afectado=empleado,
            )
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
def editar_empleado_view(request, empleado_id):
    """Modifica los datos de un empleado activo ya dado de alta."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        empleado = Usuario.objects.get(id=empleado_id, rol='empleado', is_active=True)
    except Usuario.DoesNotExist:
        messages.error(request, 'Ese empleado no existe o ya está deshabilitado.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        anteriores = {
            'nombre': empleado.first_name, 'DNI': empleado.dni,
            'correo': empleado.email, 'teléfono': empleado.telefono,
        }
        form = EditarEmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            empleado = form.save()
            nuevos = {
                'nombre': empleado.first_name, 'DNI': empleado.dni,
                'correo': empleado.email, 'teléfono': empleado.telefono,
            }
            cambios = [f'{campo}: "{anteriores[campo] or "—"}" → "{nuevos[campo] or "—"}"' for campo in nuevos if nuevos[campo] != anteriores[campo]]
            if cambios:
                _auditar(
                    request, 'edicion_empleado',
                    f'Datos de {_nombre(empleado)} modificados por {_nombre(request.user)} ({"; ".join(cambios)}).',
                    usuario_afectado=empleado,
                )
                messages.success(request, f'✓ Datos de {_nombre(empleado)} actualizados.')
            else:
                messages.info(request, 'No se modificó ningún dato.')
            return redirect('admin_dashboard')

        error = next(iter(form.errors.values()))[0] if form.errors else 'Revisá los datos ingresados.'
        contexto = _contexto_dashboard()
        contexto.update({
            'empleado_editar': Usuario.objects.get(id=empleado_id),
            'error_empleado_editar': error,
            'datos_empleado_editar': request.POST,
            'mostrar_editar_empleado': True,
        })
        return render(request, 'administrador/dashboard.html', contexto)

    contexto = _contexto_dashboard()
    contexto.update({'empleado_editar': empleado, 'mostrar_editar_empleado': True})
    return render(request, 'administrador/dashboard.html', contexto)


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
        # Si tenía un vehículo asignado, queda libre para asignarlo a otro
        # empleado — no tiene sentido que siga "ocupado" por alguien que ya
        # no puede manejarlo.
        Vehiculo.objects.filter(empleado=empleado).update(empleado=None)
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
            vehiculo = form.save()
            _auditar(
                request, 'alta_vehiculo',
                f'Alta del vehículo {vehiculo.patente} ({vehiculo.get_tipo_display()}) por {_nombre(request.user)}; '
                f'empleado asignado: {_nombre(vehiculo.empleado) if vehiculo.empleado else "sin asignar"}.',
                usuario_afectado=vehiculo.empleado,
            )
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
    (tipo semanal | mensual | personalizado, con anio/mes o desde/hasta). Se
    usa tanto para mostrarlo en pantalla como para el PDF, así ambos siempre
    muestran exactamente los mismos números."""
    tipo = request.GET.get('tipo', 'semanal')
    ahora = timezone.now()
    anio, mes = ahora.year, ahora.month
    desde = hasta = None
    error = ''

    if tipo == 'mensual':
        try:
            anio = int(request.GET.get('anio') or anio)
            mes = int(request.GET.get('mes') or mes)
            inicio = timezone.make_aware(datetime(anio, mes, 1))
            fin = timezone.make_aware(datetime(anio + 1, 1, 1) if mes == 12 else datetime(anio, mes + 1, 1))
        except (ValueError, OverflowError):
            error = 'El mes o el año indicado no es válido.'
        periodo_texto = f"Mensual — {dict(MESES).get(mes, '')} {anio}"
    elif tipo == 'personalizado':
        try:
            desde = datetime.strptime(request.GET.get('desde', ''), '%Y-%m-%d').date()
            hasta = datetime.strptime(request.GET.get('hasta', ''), '%Y-%m-%d').date()
            if desde > hasta:
                error = 'La fecha "desde" no puede ser posterior a la fecha "hasta".'
            inicio = timezone.make_aware(datetime.combine(desde, datetime.min.time()))
            fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
            periodo_texto = f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
        except ValueError:
            error = 'Indicá las fechas "desde" y "hasta" del período.'
            periodo_texto = ''
    else:
        tipo = 'semanal'
        inicio = ahora - timedelta(days=7)
        fin = ahora
        periodo_texto = f"Semanal — del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}"

    reporte = {
        'tipo': tipo,
        'anio': anio,
        'mes': mes,
        'desde': desde,
        'hasta': hasta,
        'mes_nombre': dict(MESES).get(mes, ''),
        'periodo_texto': periodo_texto,
        'generado': ahora,
        'error': error,
    }
    if error:
        return reporte

    umbral_demora = ahora - timedelta(days=Envio.UMBRAL_DEMORA_DIAS)
    # Solo cuentan los pagos efectivamente recibidos: sin anular y, si fue
    # transferencia, ya verificada por el administrador.
    pagos = Pago.objects.filter(fecha__gte=inicio, fecha__lt=fin, anulado=False, verificado=True)
    total_pagos = pagos.aggregate(total=Sum('monto'))['total'] or 0
    reporte.update({
        'inicio': inicio,
        'fin': fin,
        'envios_registrados': Envio.objects.filter(fecha_registro__gte=inicio, fecha_registro__lt=fin).count(),
        'envios_entregados': Envio.objects.filter(estado='entregado', fecha_entrega__gte=inicio, fecha_entrega__lt=fin).count(),
        'incidencias': Incidencia.objects.filter(fecha__gte=inicio, fecha__lt=fin).count(),
        'demorados_actuales': Envio.objects.filter(estado__in=Envio.ESTADOS_ACTIVOS, fecha_actualizacion__lt=umbral_demora).count(),
        'pagos_cantidad': pagos.count(),
        'pagos_total': total_pagos,
        'pagos_tarjeta': pagos.filter(medio_pago='tarjeta').aggregate(total=Sum('monto'))['total'] or 0,
        'pagos_transferencia': pagos.filter(medio_pago='transferencia').aggregate(total=Sum('monto'))['total'] or 0,
        'pagos_sin_verificar': Pago.objects.filter(fecha__gte=inicio, fecha__lt=fin, anulado=False, verificado=False).count(),
    })
    # "Demorados ahora" es una foto del momento, no del período: no cuenta
    # para decidir si el período tiene datos.
    reporte['hay_datos'] = any(reporte[k] for k in (
        'envios_registrados', 'envios_entregados', 'incidencias', 'pagos_cantidad', 'pagos_sin_verificar',
    ))
    return reporte


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
    if reporte['error']:
        messages.error(request, reporte['error'])
        return redirect('generar_reporte')

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

    elementos.append(Paragraph('Transporte Santa Marta', estilos['Title']))
    elementos.append(Paragraph('Reporte de operaciones — Sucursal Santiago del Estero', estilos['Heading2']))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph(f"<b>Período del reporte:</b> {reporte['periodo_texto']}", estilos['Normal']))
    elementos.append(Paragraph(f"<b>Fecha de generación:</b> {reporte['generado']:%d/%m/%Y %H:%M} hs", estilos['Normal']))
    elementos.append(Spacer(1, 0.8 * cm))

    if not reporte['hay_datos']:
        elementos.append(Paragraph(MENSAJE_SIN_DATOS, estilos['Normal']))
    else:
        filas = [
            ['Métrica', 'Valor'],
            ['Envíos registrados en el período', str(reporte['envios_registrados'])],
            ['Envíos entregados en el período', str(reporte['envios_entregados'])],
            ['Incidencias registradas en el período', str(reporte['incidencias'])],
            ['Envíos demorados en este momento', str(reporte['demorados_actuales'])],
            ['Pagos recibidos en el período (cantidad)', str(reporte['pagos_cantidad'])],
            ['Total cobrado en el período', f"${reporte['pagos_total']}"],
            ['   · con tarjeta', f"${reporte['pagos_tarjeta']}"],
            ['   · por transferencia', f"${reporte['pagos_transferencia']}"],
            ['Transferencias pendientes de verificar', str(reporte['pagos_sin_verificar'])],
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
        empleado_anterior = vehiculo.empleado
        form = EditarVehiculoForm(request.POST, instance=vehiculo)
        if form.is_valid():
            vehiculo = form.save()
            _auditar(
                request, 'edicion_vehiculo',
                f'Vehículo {vehiculo.patente} modificado por {_nombre(request.user)}; empleado asignado: '
                f'{_nombre(empleado_anterior) if empleado_anterior else "sin asignar"} → '
                f'{_nombre(vehiculo.empleado) if vehiculo.empleado else "sin asignar"}.',
                usuario_afectado=vehiculo.empleado or empleado_anterior,
            )
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
            vehiculo = Vehiculo.objects.select_related('empleado').get(id=vehiculo_id)
            _auditar(
                request, 'baja_vehiculo',
                f'Vehículo {vehiculo.patente} eliminado por {_nombre(request.user)}.',
                usuario_afectado=vehiculo.empleado,
            )
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
        'solicitud_cancelacion_pendiente': envio.solicitudes_cancelacion.filter(estado='pendiente').first(),
        'mostrar_detalle_envio': True,
    })
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def editar_destinatario_view(request, envio_id):
    """Corrige los datos del destinatario (nombre, contacto, modalidad y
    dirección) mientras el paquete todavía no llegó a la sucursal: solo se
    puede con el envío pendiente o en tránsito."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        envio = Envio.objects.select_related('destinatario').get(id=envio_id)
    except Envio.DoesNotExist:
        messages.error(request, 'Ese envío no existe.')
        return redirect('admin_dashboard')
    volver = redirect('detalle_envio', envio_id=envio.id)
    if request.method != 'POST':
        return volver

    if envio.estado not in ('pendiente', 'en_transito'):
        messages.error(
            request,
            f'{envio.codigo} está {envio.get_estado_display().lower()}: los datos del destinatario solo se pueden '
            'modificar mientras el envío está pendiente o en tránsito.'
        )
        return volver

    nombre = (request.POST.get('destinatario_nombre') or '').strip()
    telefono = (request.POST.get('telefono') or '').strip()
    email = (request.POST.get('email') or '').strip()
    modalidad = request.POST.get('modalidad')
    direccion = (request.POST.get('direccion') or '').strip()

    if not nombre or not telefono:
        messages.error(request, 'El nombre y el teléfono del destinatario son obligatorios.')
        return volver
    if email:
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'El email ingresado no es válido.')
            return volver
    if modalidad not in dict(Envio.MODALIDAD_CHOICES):
        messages.error(request, 'Elegí una modalidad de entrega válida.')
        return volver
    if modalidad == 'domicilio':
        if not direccion:
            messages.error(request, 'Para una entrega a domicilio tenés que indicar la dirección.')
            return volver
        if envio.peso > Vehiculo.CAPACIDAD_MAX_PESO_KG:
            messages.error(
                request,
                f'{envio.codigo} pesa {envio.peso} kg y no entra en el furgón de reparto '
                f'(máximo {Vehiculo.CAPACIDAD_MAX_PESO_KG} kg): tiene que quedar con retiro en sucursal.'
            )
            return volver
    else:
        direccion = ''

    destinatario = envio.destinatario
    antes = {
        'nombre': destinatario.get_full_name() or destinatario.first_name,
        'teléfono': destinatario.telefono,
        'email': destinatario.email,
        'modalidad': envio.get_modalidad_display(),
        'dirección': envio.direccion_entrega,
    }
    if nombre != antes['nombre']:
        destinatario.first_name = nombre
        destinatario.last_name = ''
    destinatario.telefono = telefono
    destinatario.email = email
    destinatario.save(update_fields=['first_name', 'last_name', 'telefono', 'email'])

    # Si cambia la dirección hay que volver a ubicarla en el mapa para la
    # zona de reparto, no se puede reutilizar la zona de la dirección vieja.
    if direccion != envio.direccion_entrega:
        envio.zona = ''
        envio.lat = None
        envio.lon = None
    envio.modalidad = modalidad
    envio.direccion_entrega = direccion
    envio.save()

    despues = {
        'nombre': nombre, 'teléfono': telefono, 'email': email,
        'modalidad': envio.get_modalidad_display(), 'dirección': direccion,
    }
    cambios = [f'{campo}: "{antes[campo] or "—"}" → "{despues[campo] or "—"}"' for campo in despues if despues[campo] != antes[campo]]
    if cambios:
        _auditar(
            request, 'modificacion_destinatario',
            f'Datos del destinatario del envío {envio.codigo} modificados por {_nombre(request.user)} ({"; ".join(cambios)}).',
            envio_afectado=envio, usuario_afectado=destinatario,
        )
        messages.success(request, f'✓ Se actualizaron los datos del destinatario de {envio.codigo}.')
    else:
        messages.info(request, 'No se modificó ningún dato.')
    return volver


@login_required
def cancelar_envio_view(request, envio_id):
    """Cancela un envío que todavía no salió de Buenos Aires. Una vez
    despachado ya no tiene sentido cancelarlo: ahí la vía es marcarlo
    devuelto, si corresponde."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            envio = Envio.objects.get(id=envio_id, estado='pendiente')
        except Envio.DoesNotExist:
            messages.error(request, 'Ese envío no existe o ya no se puede cancelar (ya fue despachado).')
            return redirect('admin_dashboard')

        tenia_pago = envio.pagos.filter(anulado=False, verificado=True).exists()
        envio.estado = 'cancelado'
        envio.save()
        _auditar(
            request, 'cancelacion_envio',
            f'Envío {envio.codigo} cancelado por {_nombre(request.user)}' + (' (tenía un pago confirmado: queda la devolución del dinero).' if tenia_pago else '.'),
            envio_afectado=envio, usuario_afectado=envio.destinatario,
        )
        notificar_cambio_estado(envio)
        if tenia_pago:
            messages.warning(request, f'{envio.codigo} cancelado. Atención: este envío ya tenía un pago confirmado — gestioná la devolución del dinero manualmente.')
        else:
            messages.success(request, f'✓ {envio.codigo} cancelado. Se avisó al cliente por email.')
    return redirect('admin_dashboard')


@login_required
def resolver_solicitud_cancelacion_view(request, solicitud_id):
    """El administrador aprueba o rechaza un pedido de cancelación hecho por el
    cliente (`decision` = 'aprobar' | 'rechazar'). Aprobar pasa el envío a
    cancelado; rechazar lo deja como estaba y le avisa al cliente, con el
    motivo si el administrador lo escribió. Solo se resuelve mientras el
    envío siga pendiente."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        solicitud = SolicitudCancelacion.objects.select_related('envio').get(id=solicitud_id, estado='pendiente')
    except SolicitudCancelacion.DoesNotExist:
        messages.error(request, 'Esa solicitud no existe o ya fue resuelta.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        envio = solicitud.envio
        decision = request.POST.get('decision')
        motivo = (request.POST.get('respuesta') or '').strip()

        if decision == 'aprobar':
            if envio.estado != 'pendiente':
                messages.error(request, f'{envio.codigo} ya no está pendiente (estado actual: {envio.get_estado_display()}) — no se puede cancelar.')
                return redirect('admin_dashboard')

            tenia_pago = envio.pagos.filter(anulado=False, verificado=True).exists()
            envio.estado = 'cancelado'
            envio.save()

            solicitud.estado = 'aprobada'
            solicitud.resuelto_por = request.user
            solicitud.fecha_resolucion = timezone.now()
            solicitud.save()
            _auditar(
                request, 'cancelacion_envio',
                f'Cancelación del envío {envio.codigo} aprobada por {_nombre(request.user)} a pedido del cliente '
                f'(solicitud N° {solicitud.id})' + ('; tenía un pago confirmado: queda la devolución del dinero.' if tenia_pago else '.'),
                envio_afectado=envio, usuario_afectado=envio.destinatario,
            )

            notificar_cambio_estado(envio)
            if tenia_pago:
                messages.warning(request, f'{envio.codigo} cancelado. Atención: este envío ya tenía un pago confirmado — gestioná la devolución del dinero manualmente.')
            else:
                messages.success(request, f'✓ {envio.codigo} cancelado. Se avisó al cliente por email.')

        elif decision == 'rechazar':
            solicitud.estado = 'rechazada'
            solicitud.respuesta_admin = motivo
            solicitud.resuelto_por = request.user
            solicitud.fecha_resolucion = timezone.now()
            solicitud.save()
            _auditar(
                request, 'rechazo_cancelacion',
                f'Pedido de cancelación N° {solicitud.id} del envío {envio.codigo} rechazado por {_nombre(request.user)}'
                + (f'. Motivo: {motivo}' if motivo else '.'),
                envio_afectado=envio, usuario_afectado=envio.destinatario,
            )

            notificar_solicitud_cancelacion_rechazada(solicitud)
            messages.success(request, f'Rechazaste el pedido de cancelación de {envio.codigo}. El envío sigue su curso y se avisó al cliente por email.')

        else:
            messages.error(request, 'No se indicó si aprobar o rechazar la cancelación.')

    return redirect('admin_dashboard')


@login_required
def marcar_devuelto_view(request, envio_id):
    """Da por cerrado un envío retenido que el cliente nunca pasó a retirar."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            envio = Envio.objects.get(id=envio_id, estado='retenido')
        except Envio.DoesNotExist:
            messages.error(request, 'Ese envío no existe o no está retenido en sucursal.')
            return redirect('admin_dashboard')

        envio.estado = 'devuelto'
        envio.save()
        _auditar(
            request, 'devolucion_envio',
            f'Envío {envio.codigo} marcado como devuelto a Buenos Aires por {_nombre(request.user)}.',
            envio_afectado=envio, usuario_afectado=envio.destinatario,
        )
        notificar_cambio_estado(envio)
        messages.success(request, f'✓ {envio.codigo} marcado como devuelto a Buenos Aires. Se avisó al cliente por email.')
    return redirect('admin_dashboard')


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
        respuesta = (request.POST.get('respuesta') or '').strip()
        if estado in dict(Reclamo.ESTADO_CHOICES):
            if estado == 'resuelto' and not respuesta:
                messages.error(request, 'Debe ingresar una respuesta antes de cerrar el reclamo.')
                # Se vuelve a mostrar el formulario con lo que el admin eligió,
                # sin guardar nada.
                reclamo.estado = estado
                contexto = _contexto_dashboard()
                contexto.update({'reclamo_gestionar': reclamo, 'mostrar_gestionar_reclamo': True})
                return render(request, 'administrador/dashboard.html', contexto)
            estado_anterior = reclamo.get_estado_display()
            cambio = estado != reclamo.estado or respuesta != reclamo.respuesta
            reclamo.estado = estado
            reclamo.respuesta = respuesta
            reclamo.save()
            if cambio:
                _auditar(
                    request, 'gestion_reclamo',
                    f'Reclamo N° {reclamo.id} del envío {reclamo.envio.codigo} gestionado por {_nombre(request.user)}: '
                    f'{estado_anterior} → {reclamo.get_estado_display()}'
                    + ('; con respuesta al cliente.' if respuesta else '.'),
                    envio_afectado=reclamo.envio, usuario_afectado=reclamo.cliente,
                )
                notificar_reclamo_actualizado(reclamo)
                messages.success(request, f'✓ Reclamo N° {reclamo.id} actualizado. Se avisó al cliente por email.')
        return redirect('admin_dashboard')

    contexto = _contexto_dashboard()
    contexto.update({'reclamo_gestionar': reclamo, 'mostrar_gestionar_reclamo': True})
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def configuracion_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    contexto = _contexto_dashboard()
    contexto['mostrar_configuracion'] = True
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def actualizar_perfil_admin_view(request):
    """El administrador edita sus propios datos de contacto."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        try:
            if email:
                validate_email(email)
        except ValidationError:
            messages.error(request, 'El email ingresado no es válido.')
            return redirect('admin_configuracion')
        u = request.user
        u.first_name = (request.POST.get('first_name') or '').strip()
        u.last_name = (request.POST.get('last_name') or '').strip()
        u.telefono = (request.POST.get('telefono') or '').strip()
        u.email = email
        u.save(update_fields=['first_name', 'last_name', 'telefono', 'email'])
        messages.success(request, '✓ Tus datos se actualizaron correctamente.')
    return redirect('admin_configuracion')


@login_required
def cambiar_password_admin_view(request):
    """El administrador cambia su propia contraseña (pide la actual, valida la
    nueva y mantiene la sesión abierta)."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            usuario = form.save()
            update_session_auth_hash(request, usuario)
            messages.success(request, '✓ Contraseña actualizada. Usá la nueva la próxima vez que inicies sesión.')
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('admin_configuracion')


@login_required
def responder_consulta_view(request, consulta_id):
    """El administrador lee una consulta de un cliente y la responde. La
    respuesta se guarda, se muestra en el panel del cliente y se manda por mail."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    try:
        consulta = Consulta.objects.select_related('cliente').get(id=consulta_id)
    except Consulta.DoesNotExist:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        respuesta = (request.POST.get('respuesta') or '').strip()
        if not respuesta:
            messages.error(request, 'Escribí la respuesta antes de enviarla.')
            contexto = _contexto_dashboard()
            contexto.update({'consulta_responder': consulta, 'mostrar_responder_consulta': True})
            return render(request, 'administrador/dashboard.html', contexto)
        consulta.respuesta = respuesta
        consulta.estado = 'respondida'
        consulta.respondida_por = request.user
        consulta.fecha_respuesta = timezone.now()
        consulta.save()
        notificar_consulta_respondida(consulta)
        messages.success(request, f'✓ Consulta N° {consulta.id} respondida. Se avisó al cliente por email.')
        return redirect('admin_dashboard')

    contexto = _contexto_dashboard()
    contexto.update({'consulta_responder': consulta, 'mostrar_responder_consulta': True})
    return render(request, 'administrador/dashboard.html', contexto)


@login_required
def confirmar_pago_view(request, pago_id):
    """El administrador confirma que la transferencia realmente llegó a la
    cuenta de la empresa. Hasta este momento el pago no contaba como
    recibido: el envío seguía "Debe $X" y no se podía entregar."""
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            pago = Pago.objects.get(id=pago_id, anulado=False, verificado=False)
        except Pago.DoesNotExist:
            messages.error(request, 'Ese pago no existe o ya fue verificado.')
            return redirect('admin_dashboard')

        pago.verificado = True
        pago.verificado_por = request.user
        pago.fecha_verificacion = timezone.now()
        pago.save()
        _auditar(
            request, 'confirmacion_pago',
            f'Transferencia de ${pago.monto} del envío {pago.envio.codigo} confirmada como recibida por {_nombre(request.user)}.',
            pago_afectado=pago, usuario_afectado=pago.envio.destinatario,
        )
        notificar_recibo_pago(pago)
        messages.success(request, f'✓ Transferencia de ${pago.monto} confirmada para el envío {pago.envio.codigo}.')
    return redirect('admin_dashboard')


@login_required
def anular_pago_view(request, pago_id):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        try:
            pago = Pago.objects.get(id=pago_id)
            if pago.anulado:
                messages.info(request, 'Ese pago ya estaba anulado.')
            elif pago.envio.estado != 'entregado':
                era_verificado = pago.verificado
                pago.anulado = True
                pago.save()
                LogAuditoria.objects.create(
                    accion='anulacion_pago' if era_verificado else 'rechazo_pago',
                    realizado_por=request.user,
                    pago_afectado=pago,
                    usuario_afectado=pago.envio.destinatario,
                    detalle=(
                        f'Pago de ${pago.monto} ({pago.get_medio_pago_display()}) del envío {pago.envio.codigo}, '
                        f'{"anulado" if era_verificado else "rechazado (nunca se verificó la transferencia)"} '
                        f'por {request.user.get_full_name() or request.user.username}.'
                    ),
                )
                if era_verificado:
                    messages.success(request, f'Pago de {pago.envio.codigo} anulado.')
                else:
                    notificar_pago_rechazado(pago)
                    messages.warning(request, f'Comprobante de {pago.envio.codigo} rechazado: la transferencia no se confirmó como recibida. Se avisó al cliente por email.')
            else:
                messages.error(request, 'No se puede anular el pago de un envío ya entregado.')
        except Pago.DoesNotExist:
            pass
    return redirect('admin_dashboard')