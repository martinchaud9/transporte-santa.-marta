import time

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Envio, Incidencia, Despacho
from core.zonificacion import geocodificar, calcular_zona, ordenar_ruta
from core.notificaciones import notificar_cambio_estado, notificar_intento_fallido

def _contexto_dashboard(request):
    return {
        'envios_transito': Envio.objects.filter(estado='en_transito'),
        'envios_sucursal': Envio.objects.filter(estado='en_sucursal'),
        'envios_reparto': Envio.objects.filter(estado='en_reparto'),
        'envios_retenidos': Envio.objects.filter(estado='retenido'),
        'despachos_pendientes': Despacho.objects.filter(recepcion_finalizada=False).order_by('fecha_salida'),
        'transito_sin_despacho': Envio.objects.filter(estado='en_transito', despacho__isnull=True),
        'mis_entregas': Envio.objects.filter(entregado_por=request.user).select_related('destinatario').order_by('-fecha_entrega'),
    }

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
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        nuevo_estado = request.POST.get('estado')
        estados_permitidos = ['en_reparto', 'entregado']
        try:
            envio = Envio.objects.get(id=envio_id)
            if nuevo_estado in estados_permitidos:
                if nuevo_estado == 'entregado' and not envio.puede_entregarse:
                    messages.error(
                        request,
                        f'No se puede entregar {envio.codigo}: tiene un pago pendiente de ${envio.saldo_pendiente}. '
                        'El cliente debe pagar antes de recibir el paquete.'
                    )
                    return redirect('empleado_dashboard')
                envio.estado = nuevo_estado
                envio.notificado_demora = False
                if nuevo_estado == 'entregado':
                    envio.fecha_entrega = timezone.now()
                    envio.entregado_por = request.user
                envio.save()
                notificar_cambio_estado(envio)
                if nuevo_estado == 'entregado':
                    messages.success(request, f'✓ Paquete {envio.codigo} entregado correctamente.')
                else:
                    messages.success(request, f'✓ Paquete {envio.codigo} salió a reparto.')
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
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='perdido',
                descripcion=f'Paquete reportado como perdido en la sucursal (estado previo: {envio.get_estado_display()}).',
            )
            envio.estado = 'extraviado'
            envio.save()
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
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo='perdido',
                descripcion=f'Faltante detectado al finalizar la recepción del {despacho}: el paquete no llegó con el camión.',
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
                envio.estado = 'retenido'
            else:
                envio.estado = 'en_sucursal'
            envio.notificado_demora = False
            envio.save()
            notificar_intento_fallido(envio)
            if envio.estado == 'retenido':
                messages.warning(request, f'{envio.codigo}: segundo intento fallido. El paquete queda retenido en sucursal y se notificó al cliente para que pase a retirarlo.')
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

    zonas = [
        (clave, etiqueta, ordenar_ruta(list(candidatos.filter(zona=clave))))
        for clave, etiqueta in Envio.ZONA_CHOICES
    ]
    contexto = _contexto_dashboard(request)
    contexto.update({
        'reparto_zonas': zonas,
        'reparto_sin_zona': candidatos.filter(zona=''),
        'zona_choices': Envio.ZONA_CHOICES,
        'mostrar_reparto': True,
    })
    return render(request, 'empleado/dashboard.html', contexto)

@login_required
def despachar_zona_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        zona = request.POST.get('zona')
        afectados = list(Envio.objects.filter(estado='en_sucursal', modalidad='domicilio', zona=zona))
        Envio.objects.filter(id__in=[e.id for e in afectados]).update(
            estado='en_reparto', fecha_actualizacion=timezone.now(), notificado_demora=False
        )
        for envio in afectados:
            envio.estado = 'en_reparto'
            notificar_cambio_estado(envio)
        if afectados:
            messages.success(request, f'✓ Salieron a reparto {len(afectados)} paquetes de la zona {zona.title()}. Se notificó a los clientes.')
    return redirect('empleado_preparar_reparto')

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
