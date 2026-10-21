import time
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from core.models import Envio, Incidencia, Despacho, LogAuditoria, RepartoActivo, Vehiculo
from core.zonificacion import geocodificar, calcular_zona, ordenar_ruta
from core.notificaciones import notificar_cambio_estado, notificar_intento_fallido

def _contexto_dashboard(request):
    # Mismo barrido que en el panel admin: lo que lleva más de
    # UMBRAL_RETENCION_DIAS días esperando retiro vuelve a Buenos Aires.
    for envio in Envio.devolver_retenidos_vencidos():
        notificar_cambio_estado(envio)
    return {
        'envios_transito': Envio.objects.filter(estado='en_transito'),
        'envios_sucursal': Envio.objects.filter(estado='en_sucursal'),
        'envios_reparto': Envio.objects.filter(estado='en_reparto'),
        'envios_retenidos': Envio.objects.filter(estado='retenido'),
        # Solo camiones que ya salieron de Buenos Aires (los que todavía se
        # están cargando en Casa Central no le llegan a la sucursal todavía).
        'despachos_pendientes': Despacho.objects.filter(
            fecha_salida__isnull=False, recepcion_finalizada=False
        ).order_by('fecha_salida'),
        'transito_sin_despacho': Envio.objects.filter(estado='en_transito', despacho__isnull=True),
        'mis_entregas': Envio.objects.filter(entregado_por=request.user).select_related('destinatario').order_by('-fecha_entrega'),
        # Mientras el empleado tenga al menos una zona activa a su cargo, el
        # panel manda su ubicación GPS solo, de fondo, para que el cliente
        # pueda rastrear el reparto.
        'repartos_activos': RepartoActivo.objects.filter(empleado=request.user).select_related(),
    }


def _finalizar_reparto_si_corresponde(zona):
    """Si ya no queda ningún envío en_reparto de esta zona (se entregaron
    todos o volvieron a sucursal), se cierra el reparto activo — el cliente
    deja de ver el mapa en cuanto no hay nada más que rastrear."""
    if zona and not Envio.objects.filter(estado='en_reparto', zona=zona).exists():
        RepartoActivo.objects.filter(zona=zona).delete()


def _tiene_vehiculo(empleado):
    """Para salir a reparto el empleado tiene que tener un vehículo asignado."""
    return Vehiculo.objects.filter(empleado=empleado).exists()


MENSAJE_SIN_VEHICULO = (
    'No podés salir a reparto: no tenés un vehículo asignado. '
    'Pedile al administrador que te asigne uno.'
)


def _peso_en_reparto(zona):
    """Kilos que ya lleva el furgón de esta zona (envíos actualmente en reparto)."""
    total = Envio.objects.filter(estado='en_reparto', zona=zona).aggregate(t=Sum('peso'))['t']
    return total or Decimal('0')


def _armar_viaje(zona, candidatos):
    """Decide qué paquetes de la zona salen en este viaje del furgón y cuáles
    esperan a la próxima salida. Recorre los candidatos en el orden de la ruta
    y va cargando mientras entren en la capacidad que le queda al furgón; el
    que no entra queda en sucursal para la siguiente salida de la zona.
    Devuelve (viaje, quedan, peso_viaje, capacidad_libre)."""
    libre = Vehiculo.CAPACIDAD_MAX_PESO_KG - _peso_en_reparto(zona)
    viaje, quedan, acumulado = [], [], Decimal('0')
    for envio in ordenar_ruta(list(candidatos)):
        if acumulado + envio.peso <= libre:
            viaje.append(envio)
            acumulado += envio.peso
        else:
            quedan.append(envio)
    return viaje, quedan, acumulado, libre


def _registrar_reparto_activo(zona, empleado):
    """Asegura que haya un reparto activo para esta zona a cargo de este
    empleado. Se llama tanto al despachar una zona entera (`despachar_zona_view`)
    como al pasar un envío individual a reparto a mano (`actualizar_estado_view`).
    `get_or_create` para no pisar la posición ya conocida si la zona ya
    estaba en reparto (por ejemplo, otro paquete de la misma zona que sale
    un rato después)."""
    if zona:
        RepartoActivo.objects.get_or_create(zona=zona, defaults={'empleado': empleado})

@login_required
def dashboard_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    return render(request, 'empleado/dashboard.html', _contexto_dashboard(request))

@login_required
def recepcionar_envio_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        try:
            envio = Envio.objects.get(codigo=codigo, estado='en_transito')
            envio.estado = 'en_sucursal'
            envio.fecha_recepcion = timezone.now()
            envio.notificado_demora = False
            envio.save()
            notificar_cambio_estado(envio)
            messages.success(request, f'✓ Paquete {envio.codigo} recibido correctamente. Ahora está En sucursal.')
        except Envio.DoesNotExist:
            messages.error(request, f'El código "{codigo}" no corresponde a ningún paquete en tránsito.')
    return redirect('empleado_dashboard')

@login_required
def actualizar_estado_view(request):
    """Marca un envío como entregado (en la sucursal o en la puerta del
    cliente). Salir a reparto no se hace paquete por paquete: se hace por zona
    desde "Preparar reparto" (`despachar_zona_view`)."""
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        nuevo_estado = request.POST.get('estado')
        try:
            envio = Envio.objects.get(id=envio_id)
            if nuevo_estado == 'entregado':
                if not envio.puede_entregarse:
                    messages.error(
                        request,
                        f'No se puede entregar {envio.codigo}: tiene un pago pendiente de ${envio.saldo_pendiente}. '
                        'El cliente debe pagar antes de recibir el paquete.'
                    )
                    return redirect('empleado_dashboard')
                envio.estado = 'entregado'
                envio.notificado_demora = False
                envio.fecha_entrega = timezone.now()
                envio.entregado_por = request.user
                envio.save()
                notificar_cambio_estado(envio)
                _finalizar_reparto_si_corresponde(envio.zona)
                messages.success(request, f'✓ Paquete {envio.codigo} entregado correctamente.')
        except Envio.DoesNotExist:
            messages.error(request, 'El envío no existe.')
    return redirect('empleado_dashboard')

@login_required
def recepcionar_danado_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        try:
            envio = Envio.objects.get(id=envio_id, estado='en_transito')
            envio.estado = 'en_sucursal'
            envio.fecha_recepcion = timezone.now()
            envio.notificado_demora = False
            envio.save()
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='danado',
                descripcion=f'El paquete llegó dañado en la recepción del {envio.despacho or "camión"}.',
            )
            notificar_cambio_estado(envio)
            messages.warning(request, f'{envio.codigo} recibido CON DAÑOS. Se generó la incidencia automáticamente.')
        except Envio.DoesNotExist:
            messages.error(request, 'El envío no existe o no está en tránsito.')
    return redirect('empleado_dashboard')

@login_required
def reportar_danio_view(request):
    """Reporta un daño detectado DESPUÉS de haber recepcionado el paquete."""
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        try:
            envio = Envio.objects.get(id=envio_id)
        except Envio.DoesNotExist:
            messages.error(request, 'El envío no existe.')
            return redirect('empleado_dashboard')

        if envio.tiene_danio_reportado:
            messages.info(request, f'{envio.codigo} ya tenía un daño reportado.')
        else:
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='danado',
                descripcion=f'Daño detectado después de recepcionar el paquete ({envio.despacho or "sin camión"}).',
            )
            messages.warning(request, f'Se registró el daño de {envio.codigo}. La incidencia quedó cargada automáticamente.')
    return redirect('empleado_dashboard')

@login_required
def reportar_perdida_view(request):
    """Reporta que un paquete se perdió: genera la incidencia y lo marca extraviado."""
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        try:
            envio = Envio.objects.get(id=envio_id)
        except Envio.DoesNotExist:
            messages.error(request, 'El envío no existe.')
            return redirect('empleado_dashboard')

        if envio.tiene_perdida_reportada:
            messages.info(request, f'{envio.codigo} ya figura como perdido.')
        else:
            estado_previo = envio.get_estado_display()
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='perdido',
                descripcion=f'Paquete reportado como perdido en la sucursal (estado previo: {estado_previo}).',
            )
            envio.estado = 'extraviado'
            envio.save()
            LogAuditoria.objects.create(
                accion='extravio_envio',
                realizado_por=request.user,
                envio_afectado=envio,
                usuario_afectado=envio.destinatario,
                detalle=f'Envío {envio.codigo} reportado como perdido en la sucursal (estado previo: {estado_previo}).',
            )
            messages.warning(request, f'{envio.codigo} quedó marcado como extraviado. Se generó la incidencia automáticamente.')
    return redirect('empleado_dashboard')

@login_required
def finalizar_recepcion_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        despacho_id = request.POST.get('despacho_id')
        try:
            despacho = Despacho.objects.get(id=despacho_id, recepcion_finalizada=False)
        except Despacho.DoesNotExist:
            return redirect('empleado_dashboard')

        faltantes = list(despacho.envios.filter(estado='en_transito'))
        for envio in faltantes:
            envio.estado = 'extraviado'
            envio.save()
            descripcion = f'Faltante detectado al finalizar la recepción del {despacho}: el paquete no llegó con el camión.'
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='perdido',
                descripcion=descripcion,
            )
            LogAuditoria.objects.create(
                accion='extravio_envio',
                realizado_por=request.user,
                envio_afectado=envio,
                usuario_afectado=envio.destinatario,
                detalle=descripcion,
            )
        recibidos = despacho.envios_recibidos
        despacho.recepcion_finalizada = True
        despacho.fecha_recepcion_finalizada = timezone.now()
        despacho.save()

        if faltantes:
            codigos = ', '.join(e.codigo for e in faltantes)
            messages.warning(
                request,
                f'Recepción del {despacho} finalizada: {recibidos} paquetes recibidos y {len(faltantes)} FALTANTES ({codigos}). '
                'Se generaron las incidencias de paquete perdido automáticamente.'
            )
        else:
            messages.success(request, f'✓ Recepción del {despacho} finalizada: los {recibidos} paquetes llegaron completos.')
    return redirect('empleado_dashboard')

@login_required
def marcar_ausente_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        try:
            envio = Envio.objects.get(id=envio_id, estado='en_reparto')
            envio.intentos_entrega += 1
            if envio.intentos_entrega >= Envio.MAX_INTENTOS_ENTREGA:
                # Con las 2 visitas fallidas el envío deja de ser a domicilio:
                # pasa a retiro en sucursal y el cliente tiene el plazo de
                # retención para ir a buscarlo.
                envio.estado = 'retenido'
                envio.modalidad = 'sucursal'
            else:
                envio.estado = 'en_sucursal'
            envio.notificado_demora = False
            envio.save()
            _finalizar_reparto_si_corresponde(envio.zona)
            notificar_intento_fallido(envio)
            if envio.estado == 'retenido':
                messages.warning(request, f'{envio.codigo}: segundo intento fallido. La entrega pasa a retiro en sucursal: el paquete queda retenido y el cliente tiene {Envio.UMBRAL_RETENCION_DIAS} días para retirarlo (se le notificó por email).')
            else:
                messages.success(request, f'✓ {envio.codigo}: intento de entrega registrado. El paquete vuelve a sucursal y se notificó al cliente.')
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_dashboard')

@login_required
def preparar_reparto_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    candidatos = Envio.objects.filter(estado='en_sucursal', modalidad='domicilio')

    sin_zona_previo = list(candidatos.filter(zona=''))
    fallidos = []
    for i, envio in enumerate(sin_zona_previo):
        if i > 0:
            time.sleep(1)  # respeta el límite de 1 request/segundo de Nominatim
        coordenadas = geocodificar(envio.direccion_entrega)
        if not coordenadas:
            # Nominatim puede fallar por falta de internet, demora o dirección
            # inexistente; se reintenta una vez antes de darlo por perdido.
            time.sleep(1)
            coordenadas = geocodificar(envio.direccion_entrega)
        if coordenadas:
            envio.lat, envio.lon = coordenadas
            envio.zona = calcular_zona(*coordenadas)
            envio.save()
        else:
            fallidos.append(envio.codigo)

    if fallidos:
        messages.warning(
            request,
            f'No se pudo ubicar en el mapa la dirección de {len(fallidos)} envío(s): {", ".join(fallidos)}. '
            'Puede ser por falta de internet o porque la dirección no existe. '
            'Asignales la zona a mano en el listado de abajo.'
        )

    zonas = []
    for clave, etiqueta in Envio.ZONA_CHOICES:
        viaje, quedan, peso_viaje, libre = _armar_viaje(clave, candidatos.filter(zona=clave))
        zonas.append({
            'clave': clave, 'etiqueta': etiqueta,
            'viaje': viaje, 'quedan': quedan,
            'peso_viaje': peso_viaje,
            'peso_en_reparto': _peso_en_reparto(clave),
            'capacidad': Vehiculo.CAPACIDAD_MAX_PESO_KG,
        })
    contexto = _contexto_dashboard(request)
    contexto.update({
        'reparto_zonas': zonas,
        'reparto_sin_zona': candidatos.filter(zona=''),
        'zona_choices': Envio.ZONA_CHOICES,
        'mostrar_reparto': True,
        'sin_vehiculo': not _tiene_vehiculo(request.user),
    })
    return render(request, 'empleado/dashboard.html', contexto)

@login_required
def despachar_zona_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        if not _tiene_vehiculo(request.user):
            messages.error(request, MENSAJE_SIN_VEHICULO)
            return redirect('empleado_preparar_reparto')
        zona = request.POST.get('zona')
        candidatos = Envio.objects.filter(estado='en_sucursal', modalidad='domicilio', zona=zona)
        afectados, quedan, peso_viaje, libre = _armar_viaje(zona, candidatos)
        if candidatos.exists() and not afectados:
            messages.warning(
                request,
                f'El furgón de la zona {zona.title()} está lleno ({Vehiculo.CAPACIDAD_MAX_PESO_KG - max(libre, 0)} kg de '
                f'{Vehiculo.CAPACIDAD_MAX_PESO_KG} kg). Los paquetes esperan a la próxima salida.'
            )
            return redirect('empleado_preparar_reparto')
        Envio.objects.filter(id__in=[e.id for e in afectados]).update(
            estado='en_reparto', fecha_actualizacion=timezone.now(), notificado_demora=False
        )
        for envio in afectados:
            envio.estado = 'en_reparto'
            notificar_cambio_estado(envio)
        if afectados:
            _registrar_reparto_activo(zona, request.user)
            mensaje = (
                f'✓ Salieron a reparto {len(afectados)} paquetes ({peso_viaje} kg de {Vehiculo.CAPACIDAD_MAX_PESO_KG} kg) '
                f'de la zona {zona.title()}. Se notificó a los clientes.'
            )
            if quedan:
                mensaje += f' {len(quedan)} paquete(s) no entraron en el furgón y quedan para la próxima salida de la zona.'
                messages.warning(request, mensaje)
            else:
                messages.success(request, mensaje)
    return redirect('empleado_preparar_reparto')


@login_required
def actualizar_ubicacion_view(request):
    """El celular del empleado manda acá su posición GPS cada tanto mientras
    reparte, en segundo plano (ver JS en el dashboard). Actualiza todas las
    zonas que este empleado tenga a su cargo en este momento."""
    if request.user.rol != 'empleado':
        return JsonResponse({'ok': False}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    try:
        lat = float(request.POST.get('lat'))
        lon = float(request.POST.get('lon'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Coordenadas inválidas'}, status=400)
    actualizados = RepartoActivo.objects.filter(empleado=request.user).update(
        ultima_lat=lat, ultima_lon=lon, fecha_ultima_ubicacion=timezone.now()
    )
    return JsonResponse({'ok': True, 'zonas_actualizadas': actualizados})

@login_required
def asignar_zona_manual_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        zona = request.POST.get('zona')
        zonas_validas = [clave for clave, _ in Envio.ZONA_CHOICES]
        try:
            envio = Envio.objects.get(id=envio_id)
            if zona in zonas_validas:
                envio.zona = zona
                envio.save()
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_preparar_reparto')
