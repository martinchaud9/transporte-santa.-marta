from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import Envio, Reclamo, Pago, SolicitudCancelacion
from core.forms import ModificarDatosClienteForm
from core.notificaciones import (
    notificar_recibo_pago, notificar_comprobante_recibido,
    notificar_solicitud_cancelacion_recibida,
)

COMPROBANTE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def _render_dashboard(request, **extra):
    envios = Envio.objects.filter(destinatario=request.user).order_by('-fecha_registro')
    contexto = {'envios': envios}
    contexto.update(extra)
    return render(request, 'cliente/dashboard.html', contexto)


@login_required
def dashboard_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    return _render_dashboard(request)

@login_required
def pagar_envio_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        medio = request.POST.get('medio_pago')
        try:
            envio = Envio.objects.get(id=envio_id, destinatario=request.user)
        except Envio.DoesNotExist:
            return redirect('cliente_dashboard')

        if envio.saldo_pendiente <= 0:
            messages.info(request, f'El envío {envio.codigo} ya está pagado.')
            return redirect('cliente_dashboard')
        if medio not in ('tarjeta', 'transferencia'):
            return redirect('cliente_dashboard')
        if envio.tiene_pago_pendiente_verificacion:
            # Evita que un doble clic (o un reenvío del formulario) genere
            # dos comprobantes en trámite para el mismo envío.
            messages.info(request, f'Ya hay un comprobante de {envio.codigo} esperando la verificación del administrador.')
            return redirect('cliente_dashboard')

        comprobante_foto = None
        if medio == 'tarjeta':
            # Simulación de pasarela: se validan los datos pero NO se guardan
            # ni se cobra a ninguna tarjeta real. La aprueba al instante.
            numero = (request.POST.get('tarjeta_numero') or '').replace(' ', '')
            vencimiento = request.POST.get('tarjeta_vencimiento') or ''
            cvv = request.POST.get('tarjeta_cvv') or ''
            if not (numero.isdigit() and len(numero) == 16 and len(cvv) in (3, 4) and cvv.isdigit() and vencimiento):
                messages.error(request, 'Los datos de la tarjeta no son válidos. Revisá el número (16 dígitos), el vencimiento y el código de seguridad.')
                return redirect('cliente_dashboard')
            justificacion = ''
        else:
            # Una transferencia no se confirma sola: queda pendiente hasta que
            # el administrador verifica que la plata realmente llegó.
            comprobante_numero = (request.POST.get('comprobante') or '').strip()
            comprobante_foto = request.FILES.get('comprobante_foto')
            if not comprobante_numero:
                messages.error(request, 'Ingresá el número de comprobante de la transferencia.')
                return redirect('cliente_dashboard')
            if not comprobante_foto:
                messages.error(request, 'Adjuntá una foto del comprobante de la transferencia.')
                return redirect('cliente_dashboard')
            if not comprobante_foto.content_type.startswith('image/'):
                messages.error(request, 'El archivo adjunto debe ser una imagen (foto o captura de pantalla del comprobante).')
                return redirect('cliente_dashboard')
            if comprobante_foto.size > COMPROBANTE_MAX_BYTES:
                messages.error(request, 'La imagen del comprobante no puede superar los 5 MB.')
                return redirect('cliente_dashboard')
            justificacion = f'Comprobante de transferencia N° {comprobante_numero}'

        pago = Pago.objects.create(
            envio=envio,
            registrado_por=request.user,
            monto=envio.saldo_pendiente,
            medio_pago=medio,
            justificacion=justificacion,
            comprobante_foto=comprobante_foto,
            verificado=(medio == 'tarjeta'),
        )

        if medio == 'tarjeta':
            notificar_recibo_pago(pago)
            messages.success(request, f'✓ Pago de ${pago.monto} acreditado para el envío {envio.codigo}. Te enviamos el recibo por email.')
        else:
            notificar_comprobante_recibido(pago)
            messages.success(
                request,
                f'✓ Recibimos tu comprobante de ${pago.monto} para el envío {envio.codigo}. '
                'Queda pendiente de verificación: el administrador va a confirmar que la transferencia haya llegado.'
            )
    return redirect('cliente_dashboard')


@login_required
def solicitar_cancelacion_view(request):
    """El cliente pide cancelar su propio envío mientras siga pendiente de
    despacho. No se cancela solo: queda a la espera de que el administrador
    lo autorice."""
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        motivo = (request.POST.get('motivo') or '').strip()
        try:
            envio = Envio.objects.get(id=envio_id, destinatario=request.user, estado='pendiente')
        except Envio.DoesNotExist:
            messages.error(request, 'Ese envío no existe o ya no se puede cancelar (ya fue despachado).')
            return redirect('cliente_dashboard')

        if envio.solicitudes_cancelacion.filter(estado='pendiente').exists():
            messages.info(request, f'Ya hay una solicitud de cancelación en trámite para {envio.codigo}.')
            return redirect('cliente_dashboard')

        solicitud = SolicitudCancelacion.objects.create(envio=envio, cliente=request.user, motivo=motivo)
        notificar_solicitud_cancelacion_recibida(solicitud)
        messages.success(request, f'✓ Tu solicitud de cancelación N° {solicitud.id} para {envio.codigo} fue registrada. El administrador la va a revisar a la brevedad.')
    return redirect('cliente_dashboard')


@login_required
def generar_reclamo_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        tipo = request.POST.get('tipo')
        descripcion = (request.POST.get('descripcion') or '').strip()

        if not descripcion:
            messages.error(request, 'Debés completar la descripción del reclamo, es un campo obligatorio.')
            return _render_dashboard(request, mostrar_reclamos=True)

        try:
            envio = Envio.objects.get(id=envio_id, destinatario=request.user)
        except Envio.DoesNotExist:
            messages.error(request, 'Seleccioná un envío válido para generar el reclamo.')
            return _render_dashboard(request, mostrar_reclamos=True)

        reclamo = Reclamo.objects.create(
            envio=envio,
            cliente=request.user,
            tipo=tipo,
            descripcion=descripcion,
        )
        messages.success(request, f'✓ Tu reclamo N° {reclamo.id} fue registrado. La sucursal lo va a revisar a la brevedad.')
    return redirect('cliente_dashboard')


@login_required
def modificar_datos_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        form = ModificarDatosClienteForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '✓ Tus datos se actualizaron correctamente.')
        else:
            primer_error = next(iter(form.errors.values()))[0]
            messages.error(request, primer_error)
    return redirect('cliente_dashboard')