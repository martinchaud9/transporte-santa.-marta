from django.conf import settings
from django.core.mail import send_mail

MENSAJES_ESTADO = {
    'en_transito': (
        'Tu envío salió de Buenos Aires',
        'Tu paquete {codigo} salió de Casa Central y está en camino a Santiago del Estero.',
    ),
    'en_sucursal': (
        'Tu envío llegó a la sucursal',
        'Tu paquete {codigo} llegó a la sucursal de Santiago del Estero.',
    ),
    'en_reparto': (
        'Tu envío está en reparto',
        'Tu paquete {codigo} salió a reparto.',
    ),
    'entregado': (
        'Tu envío fue entregado',
        'Tu paquete {codigo} fue entregado con éxito. ¡Gracias por elegir Santa Marta!',
    ),
}


def notificar_cambio_estado(envio):
    datos = MENSAJES_ESTADO.get(envio.estado)
    if not datos or not envio.destinatario.email:
        return
    asunto, cuerpo = datos
    send_mail(asunto, cuerpo.format(codigo=envio.codigo), settings.DEFAULT_FROM_EMAIL, [envio.destinatario.email], fail_silently=True)


def notificar_recibo_pago(pago):
    envio = pago.envio
    if not envio.destinatario.email:
        return
    lineas = [
        'Recibimos tu pago. Detalle:',
        '',
        f'  Envío: {envio.codigo}',
        f'  Monto: ${pago.monto}',
        f'  Medio de pago: {pago.get_medio_pago_display()}',
        f'  Fecha: {pago.fecha.strftime("%d/%m/%Y %H:%M") if pago.fecha else ""}',
    ]
    saldo = envio.saldo_pendiente
    if saldo > 0:
        lineas.append(f'  Saldo pendiente: ${saldo}')
    else:
        lineas.append('  Estado: Pagado en su totalidad')
    lineas.append('')
    lineas.append('¡Gracias por elegir Santa Marta!')
    send_mail(
        f'Recibo de pago — {envio.codigo}',
        '\n'.join(lineas),
        settings.DEFAULT_FROM_EMAIL,
        [envio.destinatario.email],
        fail_silently=True,
    )


def notificar_intento_fallido(envio):
    if not envio.destinatario.email:
        return
    if envio.intentos_entrega >= envio.MAX_INTENTOS_ENTREGA:
        asunto = 'Tu paquete te espera en la sucursal'
        cuerpo = (
            f'Visitamos tu domicilio para entregar el paquete {envio.codigo} y nuevamente no había nadie. '
            'Como ya se realizaron los dos intentos de entrega, el paquete quedó retenido en la sucursal '
            'de Santiago del Estero. Por favor acercate a retirarlo con tu DNI.'
        )
    else:
        asunto = 'No pudimos entregar tu paquete'
        cuerpo = (
            f'Visitamos tu domicilio para entregar el paquete {envio.codigo} pero no había nadie. '
            'En los próximos días lo visitaremos de nuevo.'
        )
    send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [envio.destinatario.email], fail_silently=True)


def notificar_demora(envio):
    if not envio.destinatario.email:
        return
    send_mail(
        'Tu envío está demorado',
        f'Tu paquete {envio.codigo} lleva más de {envio.UMBRAL_DEMORA_DIAS} días sin actualizar su estado. Estamos revisando la demora.',
        settings.DEFAULT_FROM_EMAIL,
        [envio.destinatario.email],
        fail_silently=True,
    )
