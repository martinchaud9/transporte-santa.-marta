from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import Envio, Reclamo, Pago
from core.notificaciones import notificar_recibo_pago

@login_required
def dashboard_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    envios = Envio.objects.filter(destinatario=request.user).order_by('-fecha_registro')
    return render(request, 'cliente/dashboard.html', {
        'envios': envios,
    })

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

        if medio == 'tarjeta':
            # Simulación de pasarela: se validan los datos pero NO se guardan
            # ni se cobra a ninguna tarjeta real.
            numero = (request.POST.get('tarjeta_numero') or '').replace(' ', '')
            vencimiento = request.POST.get('tarjeta_vencimiento') or ''
            cvv = request.POST.get('tarjeta_cvv') or ''
            if not (numero.isdigit() and len(numero) == 16 and len(cvv) in (3, 4) and cvv.isdigit() and vencimiento):
                messages.error(request, 'Los datos de la tarjeta no son válidos. Revisá el número (16 dígitos), el vencimiento y el código de seguridad.')
                return redirect('cliente_dashboard')
            justificacion = ''
        else:
            comprobante = (request.POST.get('comprobante') or '').strip()
            if not comprobante:
                messages.error(request, 'Ingresá el número de comprobante de la transferencia.')
                return redirect('cliente_dashboard')
            justificacion = f'Comprobante de transferencia N° {comprobante}'

        pago = Pago.objects.create(
            envio=envio,
            registrado_por=request.user,
            monto=envio.saldo_pendiente,
            medio_pago=medio,
            justificacion=justificacion,
        )
        notificar_recibo_pago(pago)
        messages.success(request, f'✓ Pago de ${pago.monto} acreditado para el envío {envio.codigo}. Te enviamos el recibo por email.')
    return redirect('cliente_dashboard')


@login_required
def generar_reclamo_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion')
        try:
            envio = Envio.objects.get(id=envio_id, destinatario=request.user)
            Reclamo.objects.create(
                envio=envio,
                cliente=request.user,
                tipo=tipo,
                descripcion=descripcion,
            )
        except Envio.DoesNotExist:
            pass
    return redirect('cliente_dashboard')